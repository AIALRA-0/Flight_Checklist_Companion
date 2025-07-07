#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MobileMain – PySide6 手机版主窗口
"""

from __future__ import annotations

import sys
import json
import shutil
import zipfile
from pathlib import Path

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtGui     import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QVBoxLayout,
    QLabel, QToolBar, QStyle, QMessageBox, QInputDialog, QComboBox, QCheckBox
)

# ———————————————————— 引用桌面版中现成的工具 / 常量 ————————————————————
from main_window import (
    ChecklistWidget, ATCWidget, ChartWidget,
    ChecklistManager, ATCManager, NotesWidget,
    ensure_dir, yes_no,                       # ← 新增
    CHECKLIST_DIR, ATC_DIR, CHART_DIR, NOTES_DIR,
    DATA_DIR, FILE_ENCODING
)


from checklist_editor import ChecklistEditor
from atc_editor import ATCEditor


class MobileMain(QMainWindow):
    # --------------------------------------------------------------------- #
    # 初始化
    # --------------------------------------------------------------------- #
    def __init__(self, ui_state: dict | None = None):
        super().__init__()
        self.setWindowTitle("Flight Checklist (Mobile)")
        self.resize(420, 720)

        # ――― 数据管理器
        self.check_mgr = ChecklistManager()
        self.atc_mgr   = ATCManager()

        # ――― 页面堆栈
        self.pages = QStackedWidget(self)
        self.setCentralWidget(self.pages)

        # ============ 页面 0：检查单 + 阶段备注 ============
        p0 = QWidget(); p0_lay = QVBoxLayout(p0)
        self.check_w     = ChecklistWidget(self.check_mgr)
        self.stage_notes = NotesWidget("阶段备注", NOTES_DIR / "stage.txt")
        p0_lay.addWidget(self.check_w)
        p0_lay.addWidget(self.stage_notes)

        # ============ 页面 1：ATC + 全局备注 ============
        p1 = QWidget(); p1_lay = QVBoxLayout(p1)
        self.atc_w       = ATCWidget(self.atc_mgr)
        self.global_notes = NotesWidget("全局备注", NOTES_DIR / "global.txt")
        p1_lay.addWidget(self.atc_w)
        p1_lay.addWidget(self.global_notes)

        # 连接信号：机型 / 阶段 改变 → 刷新 ATC
        self.check_w.ac_cmb.currentTextChanged.connect(self._ac_changed)
        self.check_w.stage_cmb.currentTextChanged.connect(self._stage_changed)

        # ============ 页面 2：航图 ============
        self.chart_w = ChartWidget(CHART_DIR)   # 需要后续刷新
        p2 = self.chart_w

        # ============ 页面 3：Checklist 编辑器 ============
        self.editor_ck = ChecklistEditor(self, self.check_mgr, "<新机型>", is_new=True)
        p3 = QWidget(); p3_lay = QVBoxLayout(p3)
        self.ck_back_btn = QAction("← 返回", self)
        self.ck_back_btn.triggered.connect(self._go_home)
        bar3 = QToolBar(); bar3.addAction(self.ck_back_btn)
        p3_lay.addWidget(bar3); p3_lay.addWidget(self.editor_ck)

        # ============ 页面 4：ATC 编辑器 ============
        self.editor_atc = ATCEditor(self, self.atc_mgr, "<机型>", "<阶段>")
        p4 = QWidget(); p4_lay = QVBoxLayout(p4)
        self.atc_back_btn = QAction("← 返回", self)
        self.atc_back_btn.triggered.connect(self._go_home)
        bar4 = QToolBar(); bar4.addAction(self.atc_back_btn)
        p4_lay.addWidget(bar4); p4_lay.addWidget(self.editor_atc)


        # === 让编辑器关闭(accept/reject)后自动跳回首页 ================
        self.editor_ck.accepted.connect(lambda: self._refresh_after_ck_save())
        self.editor_ck.rejected.connect(self._go_home)
        self.editor_atc.accepted.connect(lambda: self._refresh_after_atc_save())
        self.editor_atc.rejected.connect(self._go_home)

        # 把所有页面加入堆栈
        for page in (p0, p1, p2, p3, p4):
            self.pages.addWidget(page)

        # ――― 底部导航栏
        nav = QToolBar(); nav.setMovable(False)
        self.addToolBar(Qt.BottomToolBarArea, nav)

        from PySide6.QtWidgets import QSizePolicy

        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        nav.addWidget(spacer_left)


        def add_tab(icon, text, idx):
            act = QAction(self.style().standardIcon(icon), text, self)
            act.triggered.connect(lambda: self.pages.setCurrentIndex(idx))
            nav.addAction(act)

        add_tab(QStyle.SP_FileIcon,              "检查单", 0)
        add_tab(QStyle.SP_MessageBoxInformation, "ATC",    1)
        add_tab(QStyle.SP_DirIcon,               "航图",   2)

        nav.addWidget(spacer_right)

        self.addToolBar(Qt.BottomToolBarArea, nav)

        # ――― 顶部“航线配置”工具栏（保存 / 加载 / …）
        self.route_cmb   = QComboBox(); 
        self.route_cmb.setPlaceholderText("无航线配置")
        self.save_act    = QAction("保存",     self, triggered=self._save_route)
        self.load_act    = QAction("加载",     self, triggered=self._load_route)
        self.delete_act  = QAction("删除",     self, triggered=self._delete_route)
        self.clear_act   = QAction("清空数据", self, triggered=self._clear_all_data)
        # 创建工具栏
        route_bar = QToolBar("Routes")

        # 置顶按钮最后添加
        self.pin_cb = QCheckBox("置顶")
        self.pin_cb.setChecked(False)
        self.pin_cb.stateChanged.connect(self._toggle_stay_on_top)

        route_bar.addWidget(self.route_cmb)

        route_bar.addAction(self.save_act)
        route_bar.addAction(self.load_act)
        route_bar.addAction(self.delete_act)
        
        route_bar.addWidget(self.pin_cb)  #置顶按钮放在“删除”之后，“清空”之前
        
        route_bar.addAction(self.clear_act)
        self.switch_desktop_act = QAction("切换到桌面版", self)
        self.switch_desktop_act.triggered.connect(self._switch_to_desktop)
        route_bar.addAction(self.switch_desktop_act)
        self.addToolBar(Qt.TopToolBarArea, route_bar)
        self._refresh_routes()

        # ――― 把主按钮行为替换为页面跳转
        self.check_w._new_ac  = self._new_ck_mobile
        self.check_w._edit_ac = self._edit_ck_mobile
        self.atc_w._new_tpl   = self._new_atc_mobile
        self.atc_w._edit_tpl  = self._edit_atc_mobile

        # ――― 首次刷新一次 ATC（若已有机型）
        if self.check_w.ac_cmb.count():
            self._ac_changed(self.check_w.ac_cmb.currentText())
        
        # —— 若桌面端传来状态，立即恢复 —— #
        if ui_state:
            self._apply_ui_state(ui_state)

    def _load_stage_note(self, ac: str, stage: str):
        path = NOTES_DIR / f"{ac}_{stage}.txt"
        self.stage_notes.p = path                 # 告诉 NotesWidget 现在写哪儿
        self.stage_notes._loading = True          # 暂停 autosave 信号
        if path.exists():
            self.stage_notes.txt.setPlainText(
                path.read_text(FILE_ENCODING)
            )
        else:
            self.stage_notes.txt.clear()
        self.stage_notes._loading = False

    def _refresh_after_ck_save(self):
        """ChecklistEditor 点“保存”后：刷新并回主页，不再弹窗"""
        self.check_w._checked_memory.clear()
        self.check_w._ac_changed(self.check_w.ac_cmb.currentText())
        self.check_w._stage_changed(self.check_w.stage_cmb.currentIndex())
        self.pages.setCurrentIndex(0)           # 回主页

    def _refresh_after_atc_save(self):
        """ATCEditor 点“保存”后：刷新并回主页，不再弹窗"""
        ac    = self.check_w.ac_cmb.currentText()
        stage = self.check_w.stage_cmb.currentText()
        self.atc_w.load(ac, stage)              # 重新加载模板
        self.pages.setCurrentIndex(0)

    def _toggle_stay_on_top(self, state):
        stay_on_top = bool(state)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, stay_on_top)
        self.show()

    
    def _switch_to_desktop(self):
        """从移动版跳回桌面版，同时携带 UI 状态。"""
        from main_window import MainWindow
        self.hide()

        # —— 1. 打包当前移动端的运行时状态 —— #
        ui_state = {
            "ac"      : self.check_w.ac_cmb.currentText(),
            "stage"   : self.check_w.stage_cmb.currentText(),
            "checked" : self.check_w._checked_memory,
            "chart"   : self.chart_w.cmb.currentText(),

            #  新增：
            "page"      : self.pages.currentIndex(),
            "atc_idx"   : self.atc_w.cmb.currentIndex(),
            "stay_on_top": self.pin_cb.isChecked(),
            "route_sel" : self.route_cmb.currentText(),
        }

        # —— 2. 创建桌面主窗并恢复状态 —— #
        self._desktop_win = MainWindow()
        self._desktop_win._apply_ui_state(ui_state)   # ← 调用恢复函数
        self._desktop_win.show()

        QTimer.singleShot(0, self.close)
    
    def _apply_ui_state(self, s: dict):
        if not s:
            return
        import copy
    
        # Checklist 记忆
        self.check_w._checked_memory = copy.deepcopy(s.get("checked", {}))
        self.check_w.ac_cmb.setCurrentText(s.get("ac", ""))
        self.check_w.stage_cmb.setCurrentText(s.get("stage", ""))
        self.check_w._stage_changed(self.check_w.stage_cmb.currentIndex())
    
        # 航图
        if s.get("chart"):
            self.chart_w.cmb.setCurrentText(s["chart"])
    
        #  新增 —— ATC 模板索引
        idx = s.get("atc_idx", -1)
        if idx >= 0:
            self.atc_w.cmb.setCurrentIndex(idx)
    
        #  新增 —— 路由选项
        if s.get("route_sel"):
            self.route_cmb.setCurrentText(s["route_sel"])
    
        #  新增 —— 顶置
        self.pin_cb.setChecked(bool(s.get("stay_on_top", False)))
    
        #  新增 —— 当前页
        self.pages.setCurrentIndex(s.get("page", 0))

    # ------------------------------------------------------------------ #
    # 机型 / 阶段 切换时同步 ATC
    # ------------------------------------------------------------------ #
    def _ac_changed(self, ac: str):
        stage = self.check_w.stage_cmb.currentText()
        self.atc_w.load(ac, stage)
        self._load_stage_note(ac, stage) 

    def _stage_changed(self, stage: str):
        ac = self.check_w.ac_cmb.currentText()
        self.atc_w.load(ac, stage)
        self._load_stage_note(ac, stage) 

    # ------------------------------------------------------------------ #
    # 顶部工具栏：航线保存 / 加载 / …
    # ------------------------------------------------------------------ #
    def _refresh_routes(self):
        save_dir = Path("save"); save_dir.mkdir(exist_ok=True)
        self.route_cmb.clear()
        self.route_cmb.addItem("新建航线配置")  #  添加此项
        self.route_cmb.addItems(sorted(p.stem for p in save_dir.glob("*.zip")))

    def _save_route(self):
        cur_name = self.route_cmb.currentText().strip()
        if cur_name == "新建航线配置" or not cur_name:
            name, ok = QInputDialog.getText(self, "保存航线配置", "输入配置名称：")
            if not ok or not name.strip():
                return
            cur_name = name.strip()
        else:
            if not yes_no(self, "覆盖确认", "保存将覆盖旧版本配置，确定？"):
                return

        zip_path = ensure_dir(Path("save")) / f"{cur_name}.zip"
        if zip_path.exists() and cur_name != self.route_cmb.currentText().strip():
            if not yes_no(self, "覆盖确认", f"{cur_name} 已存在，是否覆盖？"):
                return

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder in (CHECKLIST_DIR, ATC_DIR, CHART_DIR, NOTES_DIR):
                for f in folder.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(DATA_DIR))
        QMessageBox.information(self, "完成", f"配置 {cur_name} 已保存。")
        self._refresh_routes()
        self.route_cmb.setCurrentText(cur_name)

    def _load_route(self):
        sel = self.route_cmb.currentText()
        if not sel:
            QMessageBox.information(self, "无配置", "请选择要加载的配置。")
            return
        zip_path = Path("save") / f"{sel}.zip"
        if not zip_path.exists():
            QMessageBox.warning(self, "错误", "文件不存在。")
            return
        if not yes_no(self, "加载配置", f"加载配置“{sel}”将覆盖所有当前数据，继续？"):
            return

        # 清空 data 目录
        for item in DATA_DIR.iterdir():
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(DATA_DIR)

        QMessageBox.information(self, "完成", f"配置 {sel} 已加载。")

        # 刷新界面
        self.check_w._refresh_ac(first=True)
        self._refresh_routes()
        self.chart_w._refresh(first=True)

        # 刷新全局备注显示
        self.global_notes._loading = True
        gfile = NOTES_DIR / "global.txt"
        self.global_notes.txt.setPlainText(gfile.read_text(FILE_ENCODING) if gfile.exists() else "")
        self.global_notes._loading = False

    def _delete_route(self):
        sel = self.route_cmb.currentText()
        if not sel:
            QMessageBox.information(self, "无配置", "请选择要删除的配置。")
            return
        zip_path = Path("save") / f"{sel}.zip"
        if not zip_path.exists():
            QMessageBox.warning(self, "错误", "文件不存在。")
            return
        if yes_no(self, "删除配置", f"确定删除 {sel} ？此操作不可恢复。"):
            zip_path.unlink()
            QMessageBox.information(self, "完成", "已删除。")
            self._refresh_routes()

    def _clear_all_data(self):
        if not yes_no(self, "清空确认", "确定清空所有数据？此操作不可恢复。"):
            return
        for item in DATA_DIR.iterdir():
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)
        for d in (CHECKLIST_DIR, ATC_DIR, CHART_DIR, NOTES_DIR):
            ensure_dir(d)
        QMessageBox.information(self, "完成", "已清空。")
        self.check_w._refresh_ac(first=True)
        self.chart_w._refresh(first=True)
        self.global_notes.txt.clear()
        self.route_cmb.setCurrentIndex(-1)

    # ------------------------------------------------------------------ #
    # 返回主页（带可选保存）
    # ------------------------------------------------------------------ #
    def _go_home(self):
        idx = self.pages.currentIndex()

        # ChecklistEditor 页面
        if idx == 3:
            reply = QMessageBox.question(
                self, "保存更改？", "是否保存对检查单的更改？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self.editor_ck._write_items(self.editor_ck._cur_idx)
                self.check_mgr.write(self.editor_ck.ac, self.editor_ck.data)
            self.editor_ck.is_new = False  # ← 添加这一句，避免再次 reject() 时误删

        # ATCEditor 页面
        elif idx == 4:
            # 不自动保存；返回不应触发 _save（由保存按钮决定）
            pass

        # 切回主页
        self.pages.setCurrentIndex(0)

        # 强制刷新 Checklist/ATC 状态
        ac = self.check_w.ac_cmb.currentText()
        if ac:
            self.check_w._checked_memory.clear()
            self.check_w._ac_changed(ac)
            self.check_w._stage_changed(self.check_w.stage_cmb.currentIndex())

    # ------------------------------------------------------------------ #
    # —— 检查单设置跳转（新建 / 编辑） ——
    # ------------------------------------------------------------------ #
    def _new_ck_mobile(self):
        name, ok = QInputDialog.getText(self, "机型名称", "输入新机型名称：")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self.check_mgr.list_aircraft():
            QMessageBox.warning(self, "存在", "机型已存在！")
            return

        self.check_mgr.write(name, {"stages": []})
        self.editor_ck.ac   = name
        self.editor_ck.data = {"stages": [{"name": "阶段1", "items": [""]}]}
        self.editor_ck.setWindowTitle(f"编辑检查单 – {name}")
        self.editor_ck._reload_stage_list()
        if self.editor_ck.stage_list.count():
            self.editor_ck.stage_list.setCurrentRow(0)

        self.editor_ck.show()
        self.check_w._refresh_ac(first=True)
        self.pages.setCurrentIndex(3)

    def _edit_ck_mobile(self):
        ac = self.check_w.ac_cmb.currentText()
        if not ac:
            QMessageBox.warning(self, "无机型", "当前没有可编辑的机型。")
            return
        if hasattr(self.editor_ck, "_cur_idx"):
            del self.editor_ck._cur_idx

        self.editor_ck.ac   = ac
        self.editor_ck.data = self.check_mgr.read(ac)
        self.editor_ck.setWindowTitle(f"编辑检查单 – {ac}")
        self.editor_ck._reload_stage_list()
        if self.editor_ck.stage_list.count():
            self.editor_ck.stage_list.setCurrentRow(0)

        self.editor_ck.show() 
        self.pages.setCurrentIndex(3)

    # ------------------------------------------------------------------ #
    # —— ATC 设置跳转（新建 / 编辑） ——
    # ------------------------------------------------------------------ #
    def _new_atc_mobile(self):
        ac     = self.check_w.ac_cmb.currentText()
        stage  = self.check_w.stage_cmb.currentText()
        if not ac or not stage:
            QMessageBox.warning(self, "提示", "请先选择检查单和阶段。")
            return
        self.editor_atc.ac    = ac
        self.editor_atc.stage = stage
        self.editor_atc.is_edit = False
        self.editor_atc.name_edit.setDisabled(False)
        self.editor_atc.name_edit.clear()
        self.editor_atc.cn_edit.clear()
        self.editor_atc.en_edit.clear()
        self.editor_atc.show()     
        self.pages.setCurrentIndex(4)

    def _edit_atc_mobile(self):
        if not self.atc_w.tpls:
            QMessageBox.warning(self, "无模板", "当前没有可编辑的模板")
            return
        tpl = self.atc_w.tpls[self.atc_w.cmb.currentIndex()]
        self.editor_atc.ac = tpl.get("ac", self.check_w.ac_cmb.currentText())
        self.editor_atc.stage = tpl.get("stage", self.check_w.stage_cmb.currentText())
        self.editor_atc.tpl = tpl
        self.editor_atc.is_edit = True   # ← 添加此行
        self.editor_atc.name_edit.setText(tpl.get("name", ""))
        self.editor_atc.name_edit.setDisabled(True)  # ← 禁止编辑名称
        self.editor_atc.cn_edit.setPlainText(tpl.get("cn", ""))
        self.editor_atc.en_edit.setPlainText(tpl.get("en", ""))
        self.editor_atc.show()  
        self.pages.setCurrentIndex(4)


# ———————————————————————————————————————————————————————————————— #
# CLI 入口
# ———————————————————————————————————————————————————————————————— #
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MobileMain()
    win.show()
    sys.exit(app.exec())
