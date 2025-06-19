# main_window.py
"""Main GUI for Flight Checklist Companion.

This file provides:
* data persistence managers (ChecklistManager, ATCManager)
* helper functions (ensure_dir, yes_no)
* reusable widgets: ChartView, ChartWidget, NotesWidget, ChecklistWidget, ATCWidget
* MainWindow class and CLI entry‑point

ChecklistEditor and ATCEditor live in *checklist_editor.py* and *atc_editor.py*
respectively – imported lazily when needed to avoid circular imports.
"""
from __future__ import annotations

import json
import shutil
from itertools import chain
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt, QRectF, QMimeData, QTimer
from PySide6.QtGui import QPixmap, QWheelEvent, QDragEnterEvent, QDropEvent, QPainter, QMouseEvent
from PySide6.QtWidgets import (
    QApplication, QWidget, QGroupBox, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QListWidget, QCheckBox,
    QScrollArea, QSplitter, QMessageBox, QFileDialog, QFrame, QGraphicsScene,
    QGraphicsView, QInputDialog, QDialog
)


# ──────────────────────────────────────────────────────────────────────────────
# App‑level configuration
# ──────────────────────────────────────────────────────────────────────────────
APP_TITLE = "Flight Checklist Companion"
ORG_NAME = "ExampleAviationTools"
ORG_DOMAIN = "example.com"

DATA_DIR = Path(__file__).with_suffix("").parent / "data"  # ~/flight_app/data
CHECKLIST_DIR = DATA_DIR / "checklists"
ATC_DIR = DATA_DIR / "atc"
CHART_DIR = DATA_DIR / "charts"
NOTES_DIR = DATA_DIR / "notes"
FILE_ENCODING = "utf-8"
PRIMARY_COLOR = "#2e86de"

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp")

# ──────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ──────────────────────────────────────────────────────────────────────────────

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def yes_no(parent: QWidget, title: str, text: str) -> bool:
    return (
        QMessageBox.question(parent, title, text, QMessageBox.Yes | QMessageBox.No)
        == QMessageBox.Yes
    )

# ──────────────────────────────────────────────────────────────────────────────
# JSON persistence managers
# ──────────────────────────────────────────────────────────────────────────────
class ChecklistManager:
    """Simple JSON storage `data/checklists/<ac>/checklist.json"""

    def __init__(self):
        self.root = ensure_dir(CHECKLIST_DIR)

    def list_aircraft(self) -> List[str]:
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def read(self, ac: str) -> Dict[str, Any]:
        f = self.root / ac / "checklist.json"
        return json.loads(f.read_text(FILE_ENCODING)) if f.exists() else {"stages": []}

    def write(self, ac: str, data: Dict[str, Any]):
        ensure_dir(self.root / ac).joinpath("checklist.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), FILE_ENCODING
        )

    def delete(self, ac: str):
        shutil.rmtree(self.root / ac, ignore_errors=True)


class ATCManager:
    """Simple JSON storage `data/atc/<ac>/atc.json"""

    def __init__(self):
        self.root = ensure_dir(ATC_DIR)

    def read(self, ac: str) -> Dict[str, Any]:
        f = self.root / ac / "atc.json"
        return json.loads(f.read_text(FILE_ENCODING)) if f.exists() else {"templates": []}

    def write(self, ac: str, data: Dict[str, Any]):
        ensure_dir(self.root / ac).joinpath("atc.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), FILE_ENCODING
        )

# ──────────────────────────────────────────────────────────────────────────────
# Chart viewer with zoom & pan
# ──────────────────────────────────────────────────────────────────────────────
class ChartView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene())
        self._pix_item = None
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self._zoom = 1.0
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    def set_image(self, path: Path):
        self.scene().clear()
        pix = QPixmap(str(path))
        if pix.isNull():
            return
        self._pix_item = self.scene().addPixmap(pix)
        self._pix_item.setTransformationMode(Qt.SmoothTransformation)
        self.setSceneRect(QRectF(pix.rect()))
        self.resetTransform()
        self._zoom = 1.0
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    # Ctrl+滚轮缩放
    def wheelEvent(self, e: QWheelEvent):  # noqa: N802
        if e.modifiers() & Qt.ControlModifier:
            factor = 1.15 if e.angleDelta().y() > 0 else 0.87
            self._zoom *= factor
            self.scale(factor, factor)
        else:
            super().wheelEvent(e)
    
    def clear_and_hint(self, text="无航图"):
        self.scene().clear()
        hint = self.scene().addText(text)
        hint.setDefaultTextColor(Qt.gray)
        hint.setPos(0, 0)
        self.setSceneRect(self.scene().itemsBoundingRect())
        self.centerOn(hint)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in (IMG_EXTS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, e: QDropEvent):
        added = False
        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() not in IMG_EXTS:
                QMessageBox.warning(self, "格式错误", f"{p.name} 不是支持的图片格式")
                continue

            dest = self.parent().dir / p.name  # 从 parent 获取目录
            if dest.exists():
                QMessageBox.warning(self, "重复文件", f"{p.name} 已存在")
                continue

            try:
                shutil.copy(p, dest)
                added = True
            except Exception as ex:
                QMessageBox.critical(self, "复制失败", f"{p.name} 无法复制：{ex}")

        if added:
            self.parent()._refresh(first=True)  # 让父组件刷新

        e.acceptProposedAction()
    
    def dragMoveEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in (IMG_EXTS):
                    event.acceptProposedAction()
                    return
        event.ignore()

# ──────────────────────────────────────────────────────────────────────────────
# Chart widget (right column)
# ──────────────────────────────────────────────────────────────────────────────
class ChartWidget(QGroupBox):
    def __init__(self, charts_dir: Path, parent: QWidget | None = None):
        super().__init__("航图", parent)
        self.dir = ensure_dir(charts_dir)
        self._name_map = {}
        self.setAcceptDrops(True)

        self.cmb = QComboBox()
        rename_btn = QPushButton("重命名")
        add_btn = QPushButton("添加…")
        del_btn = QPushButton("删除")
        clr_btn = QPushButton("清空")

        self.cmb.setPlaceholderText("无航图")

        hdr = QHBoxLayout()
        hdr.addWidget(self.cmb, 3)
        hdr.addWidget(add_btn)
        hdr.addWidget(del_btn)
        hdr.addWidget(rename_btn)
        hdr.addWidget(clr_btn)

        self.view = ChartView()
        self.view.setMinimumWidth(600)  # A4-ish aspect when height≈800

        lay = QVBoxLayout(self)
        lay.addLayout(hdr)
        lay.addWidget(self.view)

        # connections
        rename_btn.clicked.connect(self._rename)
        self.cmb.currentTextChanged.connect(self._show)
        add_btn.clicked.connect(self._add)
        del_btn.clicked.connect(self._del)
        clr_btn.clicked.connect(self._clear)

        self.setAcceptDrops(True)
        self._refresh(first=True)

    # file ops -----------------------------------------------------------
    def _refresh(self, first=False):
        self.cmb.blockSignals(True)
        self.cmb.clear()
        self._name_map.clear()

        imgs = sorted((p for ext in IMG_EXTS for p in self.dir.glob(f"*{ext}")), key=lambda p: p.stem.casefold())
        for p in imgs:
            display_name = p.stem
            self._name_map[display_name] = p.name  # 如 "SID1" -> "SID1.png"
            self.cmb.addItem(display_name)

        self.cmb.blockSignals(False)

        if first and imgs:
            self.cmb.setCurrentIndex(0)
            QTimer.singleShot(0, lambda: self._show(self.cmb.currentText()))
        elif not imgs:
            self.view.clear_and_hint("无航图")

    def _show(self, display_name: str):
        fname = self._name_map.get(display_name)
        if fname:
            self.view.set_image(self.dir / fname)
        else:
            self.view.clear_and_hint("无航图")

    def _add(self):
        prev = self.cmb.currentText()  # 记住当前选中项

        filter_str = "Images (" + " ".join(f"*{ext}" for ext in IMG_EXTS) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, "选择航图", str(self.dir), filter_str)
        last_added = None

        for p in paths:
            dest = self.dir / Path(p).name
            if dest.exists():
                QMessageBox.warning(self, "重复文件", f"文件 {dest.name} 已存在")
                continue
            shutil.copy(p, dest)
            last_added = Path(dest).stem  # ← 用 stem 保证能匹配 cmb 项

        self._refresh(first=False)

        if last_added:
            self.cmb.setCurrentText(last_added)  # 正确跳转显示
        elif prev in [self.cmb.itemText(i) for i in range(self.cmb.count())]:
            self.cmb.setCurrentText(prev)
        elif self.cmb.count() > 0:
            self.cmb.setCurrentIndex(0)

    def _del(self):
        if not self.cmb.count():
            QMessageBox.warning(self, "无航图", "当前没有可删除的航图。")
            return
        n = self.cmb.currentText()
        if n and yes_no(self, "删除", f"确定删除 {n} ?"):
            fname = self._name_map.get(n)
            if fname:
                (self.dir / fname).unlink(missing_ok=True)
            self._refresh(first=True)

    def _clear(self):
        imgs = list(chain.from_iterable(self.dir.glob(f"*{ext}") for ext in IMG_EXTS))
        if not imgs:
            QMessageBox.warning(self, "无航图", "当前没有可清空的航图。")
            return
        if yes_no(self, "清空", "确定删除全部航图？"):
            for p in imgs:
                p.unlink()
            self._refresh()

    # drag & drop -------------------------------------------------------
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        added = False
        last_added = None

        for url in e.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() not in IMG_EXTS:
                QMessageBox.warning(self, "格式错误", f"{p.name} 不是支持的图片格式")
                continue

            dest = self.dir / p.name
            if dest.exists():
                QMessageBox.warning(self, "重复文件", f"{p.name} 已存在，跳过导入。")
                continue

            try:
                shutil.copy(p, dest)
                last_added = dest.stem
                added = True
            except Exception as ex:
                QMessageBox.critical(self, "复制失败", f"{p.name} 无法复制：{ex}")

        if added:
            names = self._refresh(first=False)
            if last_added and last_added in names:
                self.cmb.setCurrentText(last_added)
                self._show(last_added)  # ← 手动调用，确保显示
            elif names:
                self.cmb.setCurrentIndex(0)
                self._show(names[0])

        e.acceptProposedAction()

    
    def _rename(self):
        if not self.cmb.count():
            QMessageBox.warning(self, "无航图", "当前没有可重命名的航图。")
            return
        old_name = self.cmb.currentText()
        if not old_name:
            return
        
        fname = self._name_map.get(old_name)
        if not fname:
            QMessageBox.critical(self, "错误", "无法定位原始文件。")
            return
        
        old_path = self.dir / fname
        new_name, ok = QInputDialog.getText(self, "重命名航图", "输入新文件名（不含扩展名）：")
        if not ok or not new_name.strip():
            return
        
        new_path = self.dir / (new_name.strip() + Path(fname).suffix)
        if new_path.exists():
            QMessageBox.warning(self, "文件已存在", f"{new_path.name} 已存在，请选择其他名称。")
            return
        
        try:
            old_path.rename(new_path)
        except Exception as e:
            QMessageBox.critical(self, "重命名失败", f"无法重命名文件：{e}")
            return
        
        self._refresh(first=True)
        self.cmb.setCurrentText(new_name.strip())

# ──────────────────────────────────────────────────────────────────────────────
# Notes widget (auto‑save + clear)
# ──────────────────────────────────────────────────────────────────────────────
class NotesWidget(QGroupBox):
    def __init__(self, title: str, path: Path, parent=None):
        super().__init__(title, parent)
        self.p = ensure_dir(path.parent) / path.name
        self.is_stage = "stage" in path.name  # ← 判断是阶段备注还是全局备注

        self.txt = QTextEdit()
        clr = QPushButton("清空所有阶段备注" if self.is_stage else "清空全局备注")
        clr.clicked.connect(self._clear_notes)

        lay = QVBoxLayout(self)
        lay.addWidget(self.txt)
        lay.addWidget(clr, alignment=Qt.AlignRight)

        self._loading = True
        if self.p.exists():
            self.txt.setPlainText(self.p.read_text(FILE_ENCODING))
        self._loading = False
        self.txt.textChanged.connect(self._save)

    def _save(self):
        if not self._loading:
            self.p.write_text(self.txt.toPlainText(), FILE_ENCODING)

    def _clear_notes(self):
        if self.is_stage:
            if not yes_no(self, "清空所有阶段备注", "确定删除所有阶段备注？此操作不可恢复。"):
                return
            for f in NOTES_DIR.glob("*_*.txt"):  # 阶段备注：机型_阶段.txt
                f.unlink(missing_ok=True)
            QMessageBox.information(self, "完成", "所有阶段备注已清空。")
        else:
            if not yes_no(self, "清空全局备注", "确定清空全局备注？"):
                return
            self.p.unlink(missing_ok=True)
            QMessageBox.information(self, "完成", "全局备注已清空。")

        self.txt.clear()

# ──────────────────────────────────────────────────────────────────────────────
# Checklist panel (left column)
# ──────────────────────────────────────────────────────────────────────────────
class ChecklistWidget(QGroupBox):
    def __init__(self, mgr: ChecklistManager, parent=None):
        super().__init__("检查单", parent)
        self.mgr = mgr

        self.ac_cmb = QComboBox()
        self.stage_cmb = QComboBox()
        new_btn = QPushButton("新建…")
        edit_btn = QPushButton("编辑…")
        del_btn = QPushButton("删除")

        self.ac_cmb.setPlaceholderText("无检查单")
        self.stage_cmb.setPlaceholderText("无阶段")

        hdr = QHBoxLayout()
        hdr.addWidget(self.ac_cmb, 4)      # 增加占比
        hdr.addWidget(self.stage_cmb, 3)
        hdr.addWidget(new_btn, 1)
        hdr.addWidget(edit_btn, 1)
        hdr.addWidget(del_btn, 1)

        # dynamic checklist area
        self.area = QWidget()
        self.vbox = QVBoxLayout(self.area)
        self.vbox.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.area)

        self.next_btn = QPushButton("下一阶段 →")
        self.reset_btn = QPushButton("还原检查单")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.next_btn)
        btn_row.addWidget(self.reset_btn)

        btn_row_widget = QWidget()
        btn_row_widget.setLayout(btn_row)

        lay = QVBoxLayout(self)
        lay.addLayout(hdr)
        lay.addWidget(scroll)
        lay.addWidget(btn_row_widget) 

        # signals
        self.ac_cmb.currentTextChanged.connect(self._ac_changed)
        self.stage_cmb.currentIndexChanged.connect(self._stage_changed)
        self.next_btn.clicked.connect(self._next_stage)
        new_btn.clicked.connect(self._new_ac)
        edit_btn.clicked.connect(self._edit_ac)
        del_btn.clicked.connect(self._del_ac)
        self.reset_btn.clicked.connect(self._reset_checks)
        
        self._refresh_ac(first=True)

    # CRUD --------------------------------------------------------------
    def _new_ac(self):
        from checklist_editor import ChecklistEditor  # lazy import
        name, ok = QInputDialog.getText(self, "机型名称", "输入新机型名称：")
        if not ok or not name.strip():
            return
        if name in self.mgr.list_aircraft():
            QMessageBox.warning(self, "存在", "机型已存在！")
            return
        self.mgr.write(name, {"stages": []})
        dlg = ChecklistEditor(self, self.mgr, name, is_new=True)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_ac()
            self.ac_cmb.setCurrentText(name)
            self._stage_changed(0)

    def _edit_ac(self):
        from checklist_editor import ChecklistEditor
        ac = self.ac_cmb.currentText()
        if not ac:
            QMessageBox.warning(self, "无机型", "当前没有可编辑的机型。")
            return
        ChecklistEditor(self, self.mgr, ac).exec()
        self._ac_changed(ac)

    def _del_ac(self):
        ac = self.ac_cmb.currentText()
        if not ac:
            QMessageBox.warning(self, "无机型", "当前没有可删除的机型。")
            return
        if yes_no(self, "删除机型", f"确定删除 {ac} ?"):
            self.mgr.delete(ac)
            self._refresh_ac(first=True)

    # refresh -----------------------------------------------------------
    def _refresh_ac(self, first=False):
        self.ac_cmb.blockSignals(True)
        self.ac_cmb.clear()
        self.ac_cmb.addItems(self.mgr.list_aircraft())
        self.ac_cmb.blockSignals(False)
        if first and self.ac_cmb.count():
            self.ac_cmb.setCurrentIndex(0)
            self._ac_changed(self.ac_cmb.currentText()) 
            self._stage_changed(self.stage_cmb.currentIndex())
        elif self.ac_cmb.count() == 0:
            self._populate_empty()

    def _populate_empty(self):
        self.stage_cmb.clear()
        self._clear_checks()
        self.vbox.addWidget(QLabel("无检查单", alignment=Qt.AlignCenter))
        self.next_btn.setEnabled(False)

    # stage / checks ----------------------------------------------------
    def _ac_changed(self, ac):
        data = self.mgr.read(ac)
        stages = [s["name"] for s in data.get("stages", [])]
        self.stage_cmb.blockSignals(True)
        self.stage_cmb.clear()
        self.stage_cmb.addItems(stages)
        self.stage_cmb.blockSignals(False)
        if stages:
            self.stage_cmb.setCurrentIndex(0)
        else:
            self._populate_empty()

    def _stage_changed(self, idx):
        ac = self.ac_cmb.currentText()
        data = self.mgr.read(ac)
        try:
            stage = data["stages"][idx]
        except IndexError:
            self._populate_empty()
            self.next_btn.setEnabled(False)
            return
        self._build_checks(stage["items"])

    def _build_checks(self, items):
        self._clear_checks()
        for it in items:
            cb = QCheckBox(it)
            cb.stateChanged.connect(self._update_next_btn)
            self.vbox.addWidget(cb)
        self.vbox.addStretch()
        self._update_next_btn()

    def _clear_checks(self):
        while self.vbox.count():
            itm = self.vbox.takeAt(0)
            if w := itm.widget():
                w.deleteLater()

    def _update_next_btn(self):
        ok = all(
            isinstance(self.vbox.itemAt(i).widget(), QCheckBox)
            and self.vbox.itemAt(i).widget().isChecked()
            for i in range(self.vbox.count() - 1)
        )
        self.next_btn.setEnabled(ok)

    def _next_stage(self):
        i = self.stage_cmb.currentIndex()
        if i < self.stage_cmb.count() - 1:
            self.stage_cmb.setCurrentIndex(i + 1)
        else:
            QMessageBox.information(self, "提示", "已是最后一个阶段。")

    def _reset_checks(self):
        if not yes_no(self, "还原检查单", "确定将所有阶段的所有项目标记为未完成？"):
            return

        for i in range(self.stage_cmb.count()):
            self.stage_cmb.setCurrentIndex(i)
            QApplication.processEvents()  # 强制刷新 UI
            for j in range(self.vbox.count() - 1):
                w = self.vbox.itemAt(j).widget()
                if isinstance(w, QCheckBox):
                    w.setChecked(False)

        # 回到第一个阶段
        if self.stage_cmb.count() > 0:
            self.stage_cmb.setCurrentIndex(0)

# ──────────────────────────────────────────────────────────────────────────────
# ATC widget (middle column)
# ──────────────────────────────────────────────────────────────────────────────
class ATCWidget(QGroupBox):
    def __init__(self, mgr: ATCManager, parent=None):
        super().__init__("ATC 对话", parent)
        self.mgr = mgr
        self.ac = self.stage = ""
        self.tpls = []

        self.cmb = QComboBox()
        new_btn = QPushButton("新建…")
        del_btn = QPushButton("删除") 

        self.cmb.setPlaceholderText("无可用ATC对话模板")

        hdr = QHBoxLayout()
        hdr.addWidget(self.cmb, 3)
        hdr.addWidget(new_btn)
        hdr.addWidget(del_btn)  

        self.cn = QTextEdit(readOnly=True)
        self.en = QTextEdit(readOnly=True)
        spl = QSplitter(Qt.Vertical)
        spl.addWidget(self.cn)
        spl.addWidget(self.en)

        lay = QVBoxLayout(self)
        lay.addLayout(hdr)
        lay.addWidget(spl)

        self.cmb.currentIndexChanged.connect(self._show)
        new_btn.clicked.connect(self._new_tpl)
        del_btn.clicked.connect(self._del) 

    def load(self, ac: str, stage: str):
        self.ac, self.stage = ac, stage
        data = self.mgr.read(ac)
        self.tpls = [t for t in data.get("templates", []) if t.get("stage") == stage]
        self.cmb.blockSignals(True)
        self.cmb.clear()
        self.cmb.addItems([t.get("name", "Untitled") for t in self.tpls])
        self.cmb.blockSignals(False)

        if self.tpls:
            self.cmb.setCurrentIndex(0)  # 显式设置选中第一项
        else:
            self._show(-1)

    def _show(self, idx):
        if 0 <= idx < len(self.tpls):
            self.cn.setPlainText(self.tpls[idx].get("cn", ""))
            self.en.setPlainText(self.tpls[idx].get("en", ""))
        else:
            self.cn.setPlainText("无模板")
            self.en.clear()

    def _new_tpl(self):
        from atc_editor import ATCEditor  # lazy import
        if not self.ac or not self.stage:
            QMessageBox.warning(self, "无法新建", "请先选择一个机型和阶段。")
            return
        if ATCEditor(self, self.mgr, self.ac, self.stage).exec():
            self.load(self.ac, self.stage)
        
    def _del(self):
        if not self.tpls:
            QMessageBox.warning(self, "无模板", "当前阶段没有可删除的 ATC 模板。")
            return
        idx = self.cmb.currentIndex()
        if idx < 0 or idx >= len(self.tpls):
            return
        name = self.tpls[idx].get("name", "模板")
        if not yes_no(self, "删除 ATC 模板", f"确定删除 {name} ？"):
            return
        data = self.mgr.read(self.ac)
        data["templates"].remove(self.tpls[idx])
        self.mgr.write(self.ac, data)
        self.load(self.ac, self.stage)

# ──────────────────────────────────────────────────────────────────────────────
# Main application window
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(1400, 800)

        # managers
        self.check_mgr = ChecklistManager()
        self.atc_mgr = ATCManager()

        # widgets
        self.stage_lbl = QLabel("未选择阶段", alignment=Qt.AlignCenter)
        self.stage_lbl.setStyleSheet(f"font-size:24px; color:{PRIMARY_COLOR};")
        
        # 置顶
        self.pin_cb = QCheckBox("窗口置顶")
        self.pin_cb.setChecked(True)  # 默认勾选
        self.pin_cb.stateChanged.connect(self._toggle_stay_on_top)

        grid = QGridLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(self.stage_lbl, alignment=Qt.AlignCenter)
        top_row.addStretch()
        grid.addLayout(top_row, 0, 0, 1, 3)

        self.check_w = ChecklistWidget(self.check_mgr)
        self.atc_w = ATCWidget(self.atc_mgr)
        self.chart_w = ChartWidget(CHART_DIR)
        self.stage_notes = NotesWidget("阶段备注", NOTES_DIR / "stage.txt")
        self.global_notes = NotesWidget("全局备注", NOTES_DIR / "global.txt")

        self.route_cmb = QComboBox()
        self.route_cmb.setMinimumWidth(150)
        self.route_cmb.setPlaceholderText("无航线配置")
        self.save_btn = QPushButton("保存")
        self.load_btn = QPushButton("加载")
        self.delete_btn = QPushButton("删除")  

        self.clear_btn = QPushButton("清除数据")

        top_row.addWidget(self.route_cmb)
        top_row.addWidget(self.save_btn)
        top_row.addWidget(self.load_btn)
        top_row.addWidget(self.delete_btn)
        top_row.addWidget(self.pin_cb)
        top_row.addWidget(self.clear_btn)


        self.save_btn.clicked.connect(self._save_route)
        self.load_btn.clicked.connect(self._load_route)
        self.delete_btn.clicked.connect(self._delete_route)
        self.clear_btn.clicked.connect(self._clear_all_data)

        self._refresh_routes()

        # layout
        grid.addWidget(self.stage_lbl, 0, 0, 1, 3)
        grid.addWidget(self.check_w, 1, 0)
        grid.addWidget(self.atc_w, 1, 1)
        grid.addWidget(self.chart_w, 1, 2, 2, 1)
        grid.addWidget(self.stage_notes, 2, 0)
        grid.addWidget(self.global_notes, 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)  # chart wider
        grid.setRowStretch(1, 3)

        # equal width for col 0 & 1
        equal = 500
        self.check_w.setMinimumWidth(equal)
        self.atc_w.setMinimumWidth(equal)

        # signals
        self.check_w.stage_cmb.currentTextChanged.connect(self._stage_changed)
        self.check_w.ac_cmb.currentTextChanged.connect(self._ac_changed)

        if self.check_w.ac_cmb.count():
            self._ac_changed(self.check_w.ac_cmb.currentText())

    def _load_stage_note(self, ac: str, stage: str):
        path = NOTES_DIR / f"{ac}_{stage}.txt"
        self.stage_notes.p = path
        if path.exists():
            self.stage_notes.txt.blockSignals(True)
            self.stage_notes.txt.setPlainText(path.read_text(FILE_ENCODING))
            self.stage_notes.txt.blockSignals(False)
        else:
            self.stage_notes.txt.blockSignals(True)
            self.stage_notes.txt.clear()
            self.stage_notes.txt.blockSignals(False)

    def _ac_changed(self, ac):
        stage = self.check_w.stage_cmb.currentText()
        self.atc_w.load(ac, stage)
        self._load_stage_note(ac, stage)
        QTimer.singleShot(0, lambda: self._stage_changed(self.check_w.stage_cmb.currentText()))


    def _stage_changed(self, st):
        ac = self.check_w.ac_cmb.currentText()
        label = f"{ac} - {st}" if ac and st else "未选择检查单-阶段"
        self.stage_lbl.setText(label)
        self.atc_w.load(ac, st)
        self._load_stage_note(ac, st)
    
    def _toggle_stay_on_top(self, state):
        stay_on_top = bool(state)
        flags = self.windowFlags()
        if stay_on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()  # 重新应用窗口标志

    def _refresh_routes(self):
        save_dir = Path("save")
        save_dir.mkdir(exist_ok=True)
        saves = sorted(save_dir.glob("*.zip"))
        self.route_cmb.clear()
        self.route_cmb.addItems([s.stem for s in saves])

    def _save_route(self):
        cur_name = self.route_cmb.currentText().strip()
        if cur_name:  # 已有选择，直接覆盖保存
            name = cur_name
        else:
            name, ok = QInputDialog.getText(self, "保存航线配置", "输入配置名称：")
            if not ok or not name.strip():
                return
            name = name.strip()

        save_dir = ensure_dir(Path("save"))
        zip_path = save_dir / f"{name}.zip"
        if zip_path.exists() and name != cur_name:
            if not yes_no(self, "覆盖确认", f"{name} 已存在，是否覆盖？"):
                return

        import zipfile
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder in [CHECKLIST_DIR, ATC_DIR, CHART_DIR, NOTES_DIR]:
                for f in folder.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(DATA_DIR))
        QMessageBox.information(self, "完成", f"航线配置 {name} 已保存。")
        self._refresh_routes()
        self.route_cmb.setCurrentText(name)

    def _load_route(self):
        sel = self.route_cmb.currentText()
        if not sel:
            QMessageBox.information(self, "无配置", "当前没有选择可加载的航线配置。")
            return

        zip_path = Path("save") / f"{sel}.zip"
        if not zip_path.exists():
            QMessageBox.warning(self, "错误", f"配置 {sel} 不存在")
            return

        # 清空原始 data 文件夹
        for item in DATA_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(DATA_DIR)

        QMessageBox.information(self, "完成", f"配置 {sel} 已加载")

        self.check_w._refresh_ac(first=True)
        self._refresh_routes()
        self.chart_w._refresh(first=True)

        # 强制刷新 global_notes 内容
        self.global_notes._loading = True
        global_path = NOTES_DIR / "global.txt"
        if global_path.exists():
            self.global_notes.txt.setPlainText(global_path.read_text(FILE_ENCODING))
        else:
            self.global_notes.txt.clear()
        self.global_notes._loading = False
    
    def _delete_route(self):
        sel = self.route_cmb.currentText()
        if not sel:
            QMessageBox.information(self, "无配置", "当前没有选择可删除的航线配置。")
            return
        zip_path = Path("save") / f"{sel}.zip"
        if not zip_path.exists():
            QMessageBox.warning(self, "错误", f"配置 {sel} 不存在")
            return
        if yes_no(self, "删除配置", f"确定删除配置 {sel} ？此操作不可恢复。"):
            zip_path.unlink(missing_ok=True)
            QMessageBox.information(self, "完成", f"配置 {sel} 已删除")
            self._refresh_routes()

    def _clear_all_data(self):
        if not yes_no(self, "清除确认", "确定要清除所有加载的数据？此操作不可恢复。"):
            return
        try:
            for item in DATA_DIR.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            # 重新创建空结构
            ensure_dir(CHECKLIST_DIR)
            ensure_dir(ATC_DIR)
            ensure_dir(CHART_DIR)
            ensure_dir(NOTES_DIR)

            QMessageBox.information(self, "完成", "所有数据已清除。")
            self.check_w._refresh_ac(first=True)
            self.chart_w._refresh(first=True)
            self.global_notes.txt.clear()
            self.stage_lbl.setText("未选择阶段")
            self.route_cmb.setCurrentIndex(-1)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"清除失败：{e}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry‑point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    import sys

    app = QApplication(sys.argv)
    app.setOrganizationName(ORG_NAME)
    app.setOrganizationDomain(ORG_DOMAIN)
    app.setApplicationName(APP_TITLE)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()