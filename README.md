# 🛫 Flight Checklist Companion

<div align="center">
  <img src="https://github.com/user-attachments/assets/6b26bf71-2823-4d1e-b3de-c40c95d989ad" alt="Main Window" width="200"/>
</div>

一个为模拟飞行爱好者设计的本地桌面工具，用于管理飞行前、中、后的自定义**检查单**、**ATC对话模板**、**航图** 以及 **飞行笔记**

> 📦 桌面应用，基于 [PySide6](https://doc.qt.io/qtforpython/) 实现，支持保存配置、拖拽导入图片、自动保存笔记等功能；

---

## 🖼️ 主页预览
### 桌面版
<div align="center">
  <img src="https://github.com/user-attachments/assets/e2cf2956-0b5c-4f2e-869f-e0f1c0d68b1c" alt="Main Window" width="1200"/>
</div>

### 移动版
<div align="center">
  <img src="https://github.com/user-attachments/assets/f000ebed-fe83-4c81-a2e6-e7a142e4ab0e" alt="Main Window" width="600"/>
</div>


---

## 📋 功能概览

### ✅ 检查单（Checklist）

- 用于创建、编辑和运行机型的阶段性检查项：
- 支持多个机型配置，数据独立存储；
- 每个机型可定义多个飞行阶段；
- 可选分支节点：
  - 某些检查项可以设为“可选项”，其子项仅在勾选后才启用；
  - 未勾选的可选项，其子项将被禁用并置灰，防止误操作；
- 自动颜色反馈：
  - 可选项未勾选为灰色，勾选后恢复黑色；
  - 强制项恒为黑色，强调必须执行；
- 可视化编辑器：
  - 内置图形编辑器，支持增删改任意阶段与子项；
- 提供导出与导入功能，方便备份或共享检查单模板。
- 所有检查项以复选框显示，便于实时打勾；
- 检查完成后可一键跳转至“下一阶段”；
- 支持一键完成阶段；
- 支持“还原”操作，一键重置所有阶段为未勾选；
- 可导出/保存整个机型检查单结构，便于管理。

**界面示意：**

<div align="center">
  <img src="https://github.com/user-attachments/assets/ae0333cc-84bd-4e5c-9749-d5e3dfd1329b" alt="Main Window" width="600"/>
</div>


<div align="center">
  <img src="https://github.com/user-attachments/assets/b4146644-4065-48d7-aa2c-584390fb31d5" alt="Main Window" width="600"/>
</div>


---

### ✈️ ATC 对话模板（ATC Templates）

适用于飞行通信训练，按机型-阶段组织：

- 每个机型的每个阶段可配置多条通信模板
- 模板保存后可在主界面按阶段快速查看
- 中文、英文内容可分别填写，支持单语使用
- 支持删除不需要的模板

**界面示意：**

<div align="center">
  <img src="https://github.com/user-attachments/assets/920a426a-407d-4599-8540-f6e3f2ec3c36" alt="Main Window" width="600"/>
</div>

<div align="center">
  <img src="https://github.com/user-attachments/assets/795ca777-6fbf-4fc2-b035-2ba40135b68b" alt="Main Window" width="600"/>
</div>

---

### 🗺️ 航图管理（Charts）

集中查看飞行航图，支持：

- 支持 PNG, JPG, BMP 等格式
- 支持拖拽导入图片文件或使用按钮导入
- 重命名 / 删除 / 清空航图
- 自动匹配文件名为展示名称

**界面示意：**

<div align="center">
  <img src="https://github.com/user-attachments/assets/72892d84-271d-4ea6-a269-09855d857eb2" alt="Main Window" width="600"/>
</div>

---

### 📝 备注系统（Notes）

- 阶段备注：与检查单绑定，按“机型-阶段”自动保存，适合写入特定阶段注意事项
- 全局备注：不随阶段切换，适合写入任务概览、重要通知、ATIS等信息
- 支持自动保存 / 清空内容
- 可分别清空全局备注或所有阶段备注

**界面示意：**

<div align="center">
  <img src="https://github.com/user-attachments/assets/5893556e-0035-41d8-b6ac-6fe08a987f90" alt="Main Window" width="1200"/>
</div>

---

### 💾 航线配置保存（Route Save/Load）

可将所有数据打包为配置文件，便于任务切换或数据迁移：

- 支持命名保存多个不同任务配置；
- 可从下拉列表快速加载历史配置；
- 支持删除配置，清理无用数据；
- 所有数据备份均保存在本地，无需联网。
- ⚠️注意，加载会清除当前的数据，请记得保存

**界面示意：**

<div align="center">
  <img src="https://github.com/user-attachments/assets/62e0052b-4a41-4326-8138-0c7e768746c5" alt="Notes" width="600"/>
</div>

---
### 🧳 航线配置模板（Route Template Packs）

不定期提供不同机型/场景的示例配置包，便于快速体验和参考使用。

- 当前可用示例：
  - `B777.zip`：波音 777 启动检查单
      
    <img src="https://github.com/user-attachments/assets/e4998c76-9393-4856-afec-2a4ea129e1c9" alt="B777 示例" width="600"/>
  - `B737.zip`：波音 737 启动检查单
      
    <img src="https://github.com/user-attachments/assets/3d77cb23-2590-4425-a064-5f229da0f831" alt="B737 示例" width="600"/>

#### 使用方式：

1. 将所需的示例配置包放入项目目录下的 `save/` 文件夹；
2. 启动程序后，在航线配置下拉框中即可看到该任务；
3. 选择并加载即可应用对应配置内容。
> ⚠️ 加载示例配置将清除当前工作数据，请提前保存。

---
## 🧩 项目结构

```bash
.
├── main_window.py        # 主窗口及主要控件
├── checklist_editor.py   # 检查单编辑器
├── atc_editor.py         # ATC 模板编辑器
├── data/                 # 存储用户数据
│   ├── checklists/
│   ├── atc/
│   ├── charts/
│   └── notes/
├── save/                 # 航线配置（ZIP）
````

---

## 🛠️ 开发依赖

* Python 3.9+
* PySide6

---

## 🙌 致谢

感谢 Qt 团队和开源社区提供的强大支持；

---

## 📌 数据说明

本项目为本地离线工具，不依赖网络、不上传任何数据，所有内容均保存在本地 `data` 目录中；适用于飞行训练、模拟飞行、ATC 通信练习等场景，可自由扩展和定制；

---

## ⚠️ **注意事项**
- 本工具为个人开发，尚未经过完整系统性测试；
- 使用过程中可能存在 BUG 或不稳定行为；
- 示例内容由AI自动生成，不具有参考价值

🙋‍♂️ 若你在使用中遇到任何问题，欢迎提交 issue 或直接联系作者反馈；



