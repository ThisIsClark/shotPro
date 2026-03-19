---
title: Shot Improvement API
emoji: 🏀
colorFrom: yellow
colorTo: yellow
sdk: docker
pinned: false
app_port: 7860
---

# 🏀 投篮姿势分析 API

这是一个基于 FastAPI 和 MediaPipe 的投篮姿势分析后端服务。

## 功能

- **上传视频**：分析投篮动作的关键帧（准备、举球、出手、跟随）。
- **姿势评估**：基于标准动作（如 Curry 的投篮模板）进行评分和建议。
- **PDF 报告**：生成详细的分析报告。

## 部署说明

本项目已配置为直接部署到 Hugging Face Spaces (Docker SDK)。

1. 在 Hugging Face 创建一个新的 Space。
2. 选择 **Docker** 作为 SDK。
3. 将本项目代码推送到 Space 的仓库中。
4. 等待构建完成即可使用。

API 文档地址：`https://<你的Space地址>.hf.space/docs`
