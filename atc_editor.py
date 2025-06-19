#!/usr/bin/env python3
"""
ATCEditor – 新建 ATC 对话模板
依赖 main_window.py 中的 ATCManager。
"""
from __future__ import annotations
from PySide6.QtCore   import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QTextEdit, QLabel, QVBoxLayout, QPushButton, QMessageBox
)

from main_window import ATCManager


class ATCEditor(QDialog):
    def __init__(self, parent, mgr: ATCManager, aircraft: str, stage: str):
        super().__init__(parent)
        self.setWindowTitle("新建 ATC 模板")
        self.resize(420, 320)

        self.mgr, self.ac, self.stage = mgr, aircraft, stage

        self.name_edit = QLineEdit()
        self.cn_edit = QTextEdit()
        self.en_edit = QTextEdit()
        save_btn = QPushButton("保存")

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("模板名称"))
        lay.addWidget(self.name_edit)
        lay.addWidget(QLabel("中文内容"))
        lay.addWidget(self.cn_edit)
        lay.addWidget(QLabel("英文内容"))
        lay.addWidget(self.en_edit)
        lay.addWidget(save_btn, alignment=Qt.AlignRight)

        save_btn.clicked.connect(self._save)

    from PySide6.QtWidgets import QMessageBox  # 确保顶部有这行

    def _save(self):
        name = self.name_edit.text().strip()
        cn = self.cn_edit.toPlainText().strip()
        en = self.en_edit.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "标题缺失", "模板名称不能为空。")
            return
        if not cn and not en:
            QMessageBox.warning(self, "内容缺失", "中文内容和英文内容不能同时为空。")
            return
        
        # 重复名称检查
        existing_names = [
            t["name"] for t in self.mgr.read(self.ac).get("templates", [])
            if t.get("stage") == self.stage
        ]
        if name in existing_names:
            QMessageBox.warning(self, "重复名称", "该模板名称在当前阶段已存在。")
            return

        data = self.mgr.read(self.ac)
        data.setdefault("templates", []).append({
            "name": name,
            "stage": self.stage,
            "cn": cn,
            "en": en
        })
        self.mgr.write(self.ac, data)
        self.accept()