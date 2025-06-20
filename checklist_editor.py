#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChecklistEditor – 编辑机型检查单的对话窗口（新增、删除阶段与检查项）

本模块提供一个用于管理飞行检查单的 GUI 对话框，支持以下功能：
- 按阶段组织检查项目（如：启动、滑行、起飞等）
- 每阶段下可添加多个检查项，支持逐行编辑、添加、删除
- 阶段名称可重命名，至少保留一个阶段和一项
- 自动保存并写入到 ChecklistManager 中

依赖项：
- main_window.py 中的 ChecklistManager 和 yes_no 工具函数
- 使用 PySide6 构建界面

用例：
从主程序中以模态对话框方式调用 ChecklistEditor，实现检查单的增删改管理
"""

from __future__ import annotations
from typing import List

from PySide6.QtCore   import Qt
from PySide6.QtWidgets import (
    QDialog, QListWidget, QListWidgetItem, QWidget, QLineEdit, QToolButton,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QInputDialog, QMessageBox,
    QCheckBox
)

from main_window import ChecklistManager, yes_no


# ────────────────────── 行控件（输入框 + ＋/－按钮） ──────────────────────
class _TreeItemRow(QWidget):
    """
    单行输入组件：
      [↖] [↘]  ➜ 调整层级（左=减少缩进，右=增加缩进）
      [+] [－] ➜ 同级增 / 删
      [☑]      ➜ Optional?  勾选=可选项目
      QLineEdit ➜ 文本
    保存到 QListWidget.itemData(Qt.UserRole)：
      {"text": str, "level": int, "optional": bool}
    """
    INDENT = 20  # 像素

    def __init__(self, lw: QListWidget, data: dict | None = None):
        super().__init__()
        self.lw = lw
        d = data or {"text": "", "level": 0, "optional": False}

        self.left  = QToolButton(); self.left.setText("↖")
        self.right = QToolButton(); self.right.setText("↘")
        add        = QToolButton(); add.setText("＋")
        rem        = QToolButton(); rem.setText("－")
        self.opt   = QCheckBox("可选")
        self.opt.setChecked(d["optional"])
        self.line  = QLineEdit(d["text"])
        self.opt.stateChanged.connect(self._cascade_optional)

        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        for w in (self.line, self.opt, self.left, self.right, add, rem): lay.addWidget(w)

        # 信号
        add.clicked.connect(self._add_after)
        rem.clicked.connect(self._remove)
        self.left.clicked.connect(lambda: self._indent(-1))
        self.right.clicked.connect(lambda: self._indent(+1))

        # 根据 level 缩进
        self._apply_indent(d["level"])

    # ---------- 列表定位 ----------
    def _row(self) -> int:
        for i in range(self.lw.count()):
            if self.lw.itemWidget(self.lw.item(i)) is self:
                return i
        return -1

    # ---------- 按钮动作 ----------
    def _add_after(self):
        idx = self._row()
        cur_item = self.lw.item(idx)
        cur_data = cur_item.data(Qt.UserRole) or {"level": 0, "optional": False}
        cur_level = cur_data.get("level", 0)
        cur_optional = cur_data.get("optional", False)
    
        # 计算新项的层级：若当前项有子项 → 插入第一子项的层级；否则维持当前层级
        new_level = cur_level
        if idx + 1 < self.lw.count():
            next_item = self.lw.item(idx + 1)
            next_level = (next_item.data(Qt.UserRole) or {}).get("level", 0)
            if next_level > cur_level:
                new_level = next_level
    
        itm = QListWidgetItem()
        self.lw.insertItem(idx + 1, itm)
    
        row = _TreeItemRow(self.lw, {
            "text": "",
            "level": new_level,
            "optional": cur_optional
        })
    
        itm.setData(Qt.UserRole, {
            "text": "",
            "level": new_level,
            "optional": cur_optional
        })
        itm.setSizeHint(row.sizeHint())
        self.lw.setItemWidget(itm, row)
        
    def _remove(self):
        if self.lw.count() == 1:
            return

        idx = self._row()
        cur_item = self.lw.item(idx)
        cur_level = (cur_item.data(Qt.UserRole) or {}).get("level", 0)

        # 向下查找所有子项（比当前层级更深的项）
        descendents = []
        for i in range(idx + 1, self.lw.count()):
            item = self.lw.item(i)
            level = (item.data(Qt.UserRole) or {}).get("level", 0)
            if level <= cur_level:
                break
            descendents.append((i, item, level))

        # 所有子项层级前移 1（不小于 0），并恢复复选框可操作性
        for i, item, level in descendents:
            new_level = max(0, level - 1)
            data = item.data(Qt.UserRole) or {}
            data["level"] = new_level
            item.setData(Qt.UserRole, data)

            roww = self.lw.itemWidget(item)
            roww._apply_indent(new_level)
            roww.opt.setEnabled(True)  # ← 恢复可编辑状态
            roww._sync_optional_with_parent(i)  # ← 重查找新父节点

        # 删除当前项
        self.lw.takeItem(idx)
        
    def _indent(self, delta: int):
        idx = self._row()
        itm = self.lw.item(idx)
        data = itm.data(Qt.UserRole) or {"level": 0}
        cur_level = data["level"]
        new_level = cur_level + delta
        

        # 确保同步父项的可选性，如果当前项变成顶层或父项不可选→取消勾选
        if new_level == 0:
            self.opt.setChecked(False)
            data["optional"] = False  # ← 关键更新：同步 optional
        else:
            # 查找新的父项
            for i in range(idx - 1, -1, -1):
                pitem = self.lw.item(i)
                pl = (pitem.data(Qt.UserRole) or {}).get("level", 0)
                if pl < new_level:
                    prow = self.lw.itemWidget(pitem)
                    if not prow.opt.isChecked():
                        self.opt.setChecked(False)
                    break
        if new_level == 0:
            self.opt.setChecked(False)
               
        if new_level < 0:
            QMessageBox.warning(self, "缩进无效", "不能缩进到负层级。")
            return
    
        # 第一项必须是顶层（level == 0）
        if idx == 0 and new_level != 0:
            QMessageBox.warning(self, "缩进无效", "第一项必须为顶层，不能缩进。")
            return
        

        # 获取上一行的 level
        if idx > 0:
            prev_item = self.lw.item(idx - 1)
            prev_level = (prev_item.data(Qt.UserRole) or {}).get("level", 0)
        else:
            prev_level = 0  # 第一行必须是顶级

        # 获取所有行中的最小层级
        min_level = min(
            (self.lw.item(i).data(Qt.UserRole) or {}).get("level", 0)
            for i in range(self.lw.count())
        )

        # 校验规则：
        if new_level > prev_level + 1:
            QMessageBox.warning(
                self, "缩进无效",
                f"违反缩进规则"
            )
            return

        delta_level = new_level - cur_level

        # 更新当前项
        data["level"] = new_level
        itm.setData(Qt.UserRole, data)
        self._apply_indent(new_level)

        # 向下查找所有子项并同步调整缩进
        for i in range(idx + 1, self.lw.count()):
            item = self.lw.item(i)
            level = (item.data(Qt.UserRole) or {}).get("level", 0)
            if level <= cur_level:
                break
            new_child_level = max(0, level + delta_level)
            child_data = item.data(Qt.UserRole) or {}
            child_data["level"] = new_child_level
            item.setData(Qt.UserRole, child_data)
            roww = self.lw.itemWidget(item)
            roww._apply_indent(new_child_level)

        self._sync_optional_with_parent(idx)

    # ---------- 导出数据 ----------
    def export(self) -> dict:
        return {
            "text": self.line.text().strip(),
            "level": (self.lw.item(self._row()).data(Qt.UserRole) or {}).get("level", 0),
            "optional": self.opt.isChecked(),
        }
    
    def _apply_indent(self, level: int):
        self.line.setStyleSheet(f"margin-left:{level * self.INDENT}px;")
    
    def _sync_optional_with_parent(self, idx: int):
        level = (self.lw.item(idx).data(Qt.UserRole) or {}).get("level", 0)
        for i in range(idx - 1, -1, -1):
            parent_item = self.lw.item(i)
            pl = (parent_item.data(Qt.UserRole) or {}).get("level", 0)
            if pl < level:
                parent_row = self.lw.itemWidget(parent_item)
    
                if parent_row.opt.isChecked():
                    # 父节点本身就是可选 → 子节点被强制可选并锁定
                    self.opt.setChecked(True)
                    self.opt.setEnabled(False)
                else:
                    # 父节点不是可选 → 子节点维持原状态，只是保持可编辑
                    self.opt.setEnabled(True)
                break
        else:
            # 没找到父节点（顶层）
            self.opt.setEnabled(True)

    def _cascade_optional(self, state: int):
        idx = self._row()
        level = (self.lw.item(idx).data(Qt.UserRole) or {}).get("level", 0)

        # 仅处理子项，当前项不变
        for i in range(idx + 1, self.lw.count()):
            item = self.lw.item(i)
            ilev = (item.data(Qt.UserRole) or {}).get("level", 0)
            if ilev <= level:
                break
            row = self.lw.itemWidget(item)
            row.opt.setChecked(bool(state))
            row.opt.setEnabled(not state)  # 锁定为可选状态时禁用交互

# ───────────────────────────── 编辑器对话框 ─────────────────────────────
class ChecklistEditor(QDialog):
    """可视化编辑一个机型的多阶段检查单"""

    def __init__(self, parent, mgr: ChecklistManager, aircraft: str, is_new=False):
        super().__init__(parent)
        self.setWindowTitle(f"编辑检查单 – {aircraft}")
        self.resize(820, 420)

        self.is_new = is_new

        self.mgr, self.ac = mgr, aircraft
        self.data = mgr.read(aircraft)

        # 左侧阶段列表
        self.stage_list = QListWidget()
        add_stage = QPushButton("添加阶段")
        del_stage = QPushButton("删除阶段")

        # 右侧项目列表
        self.item_list = QListWidget()
        save_btn = QPushButton("保存并关闭")

        # ------------ 布局 ------------
        left = QVBoxLayout()
        left.addWidget(QLabel("阶段"))
        left.addWidget(self.stage_list)
        left.addWidget(add_stage)
        left.addWidget(del_stage)

        right = QVBoxLayout()
        right.addWidget(QLabel("检查项目"))
        right.addWidget(self.item_list)
        right.addWidget(save_btn, alignment=Qt.AlignRight)

        root = QHBoxLayout(self)
        root.addLayout(left)
        root.addLayout(right, 1)

        # ------------ 初始化 ------------
        if not self.data["stages"]:
            self.data["stages"].append({"name": "阶段1", "items": [""]})  # 默认 1 空项目
        for st in self.data["stages"]:
            item = QListWidgetItem(st["name"])
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.stage_list.addItem(item)
        self.stage_list.setCurrentRow(0)
        self._stage_changed(0)

        # ------------ 连接信号 ------------
        self.stage_list.currentRowChanged.connect(self._stage_changed)
        add_stage.clicked.connect(self._add_stage)
        del_stage.clicked.connect(self._del_stage)
        save_btn.clicked.connect(self._save_and_close)

    def reject(self):
        # 点击“×”时退出，若是新建流程则移除文件夹
        if self.is_new:
            from shutil import rmtree
            rmtree(self.mgr.root / self.ac, ignore_errors=True)
        self.done(0)

    # 阶段切换
    def _stage_changed(self, row: int):
        if row < 0:
            return

        # 切换前保存旧阶段
        if hasattr(self, "_cur_idx"):
            self._write_items(self._cur_idx)

        self._cur_idx = row
        self.item_list.clear()

        # 若当前阶段没有任何项目→补 1 空项目
        if not self.data["stages"][row]["items"]:
            self.data["stages"][row]["items"].append("")

        for txt in self.data["stages"][row]["items"]:
            if isinstance(txt, str):
                txt = {"text": txt, "level": 0, "optional": False}  # ← 添加这句
            itm = QListWidgetItem()
            itm.setData(Qt.UserRole, txt)
            self.item_list.addItem(itm)
            row_widget = _TreeItemRow(self.item_list, txt)
            itm.setSizeHint(row_widget.sizeHint())
            self.item_list.setItemWidget(itm, row_widget)
        
        for i in range(self.item_list.count()):
            roww = self.item_list.itemWidget(self.item_list.item(i))
            roww._sync_optional_with_parent(i)   # 关键：触发灰化 / 继承

    # 添加阶段
    def _add_stage(self):
        name, ok = QInputDialog.getText(self, "阶段名称", "名称：")
        if ok and name.strip():
            self._write_items(self._cur_idx)  # 保存当前阶段的项目
            self.data["stages"].append({"name": name.strip(), "items": [""]})
            item = QListWidgetItem(name.strip())
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.stage_list.addItem(item)
            new_idx = self.stage_list.count() - 1
            self.stage_list.setCurrentRow(new_idx)  # 触发 _stage_changed(new_idx)

    # 删除阶段
    def _del_stage(self):
        if self.stage_list.count() <= 1:
            QMessageBox.warning(self, "不可删除", "至少保留一个阶段。")
            return

        row = self.stage_list.currentRow()
        if row >= 0 and yes_no(self, "删除阶段", "确定删除该阶段？"):
            self.stage_list.takeItem(row)
            self.data["stages"].pop(row)
            if self.stage_list.count():
                self.stage_list.setCurrentRow(0)

    # 把项目列表写回 data
    def _write_items(self, idx: int):
        items = []
        for i in range(self.item_list.count()):
            roww = self.item_list.itemWidget(self.item_list.item(i))
            items.append(roww.export())
        # 过滤空文本
        items = [it for it in items if it["text"]] or [{"text": "", "level": 0, "optional": False}]
        self.data["stages"][idx]["items"] = items

    # 保存并关闭
    def _save_and_close(self):
        self._write_items(self._cur_idx)

        # 保存阶段名称修改
        for i in range(self.stage_list.count()):
            name = self.stage_list.item(i).text().strip()
            if not name:
                QMessageBox.warning(self, "错误", "阶段名称不能为空")
                return
            self.data["stages"][i]["name"] = name

        # 检查所有阶段是否都有非空项目
        for stage in self.data["stages"]:
            if not any(i["text"].strip() for i in stage["items"]):
                QMessageBox.warning(self, "空项目", f"阶段 “{stage['name']}” 中没有有效的检查项。请至少填写一项。")
                return

        self.mgr.write(self.ac, self.data)
        self.accept()
    
