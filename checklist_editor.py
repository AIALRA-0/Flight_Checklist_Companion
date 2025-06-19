#!/usr/bin/env python3
"""
ChecklistEditor – 新建 / 编辑机型检查单（逐行增删项，保证至少 1 条）
依赖 main_window.py 内的 ChecklistManager 与 yes_no。
"""
from __future__ import annotations
from typing import List

from PySide6.QtCore   import Qt
from PySide6.QtWidgets import (
    QDialog, QListWidget, QListWidgetItem, QWidget, QLineEdit, QToolButton,
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QInputDialog, QMessageBox
)

from main_window import ChecklistManager, yes_no


# ────────────────────── 行控件（输入框 + ＋/－按钮） ──────────────────────
class _ItemRow(QWidget):
    """
    单行输入组件：QLineEdit + “＋” (在本行下方插入) + “－” (删除本行，
    但列表剩 1 行时禁用删除)
    """
    def __init__(self, lw: QListWidget, text: str = ""):
        super().__init__()
        self.lw = lw
        self.line = QLineEdit(text)

        add = QToolButton(); add.setText("＋")
        rem = QToolButton(); rem.setText("－")

        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.line, 1)
        lay.addWidget(add)
        lay.addWidget(rem)

        add.clicked.connect(self._add_after)
        rem.clicked.connect(self._remove)

    # 计算当前行索引
    def _row(self) -> int:
        for i in range(self.lw.count()):
            if self.lw.itemWidget(self.lw.item(i)) is self:
                return i
        return -1

    # 在当前行**下方**插入
    def _add_after(self):
        idx = self._row()
        itm = QListWidgetItem()
        self.lw.insertItem(idx + 1, itm)
        row = _ItemRow(self.lw)
        itm.setSizeHint(row.sizeHint())
        self.lw.setItemWidget(itm, row)

    # 删除当前行（若只剩 1 行则禁止）
    def _remove(self):
        if self.lw.count() == 1:
            # 保证至少一项，直接返回
            return
        self.lw.takeItem(self._row())


# ───────────────────────────── 编辑器对话框 ─────────────────────────────
class ChecklistEditor(QDialog):
    """可视化编辑一个机型的多阶段检查单"""

    def __init__(self, parent, mgr: ChecklistManager, aircraft: str, is_new=False):
        super().__init__(parent)
        self.setWindowTitle(f"编辑检查单 – {aircraft}")
        self.resize(600, 420)

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
        right.addWidget(QLabel("项目（每行一条）"))
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
            itm = QListWidgetItem()
            self.item_list.addItem(itm)
            row_widget = _ItemRow(self.item_list, txt)
            itm.setSizeHint(row_widget.sizeHint())
            self.item_list.setItemWidget(itm, row_widget)

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
        items: List[str] = []
        for i in range(self.item_list.count()):
            roww = self.item_list.itemWidget(self.item_list.item(i))
            txt = roww.line.text().strip() if roww else ""
            items.append(txt)
        # 过滤空白但保留至少 1 项
        items = [i for i in items if i] or [""]
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
            if not any(i.strip() for i in stage["items"]):
                QMessageBox.warning(self, "空项目", f"阶段 “{stage['name']}” 中没有有效的检查项。请至少填写一项。")
                return

        self.mgr.write(self.ac, self.data)
        self.accept()