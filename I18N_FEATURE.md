# 国际化功能说明

## ✨ 新增功能

系统现在支持中英文切换，用户可以通过右上角的语言切换按钮在中文和英文之间自由切换。

## 🎯 功能特点

### 1. **一键切换**
- 界面右上角有一个醒目的语言切换按钮 🌐
- 点击按钮即可在中文（zh-CN）和英文（en-US）之间切换
- 按钮显示当前可切换到的语言（显示 "EN" 表示可以切换到英文）

### 2. **记忆功能**
- 使用 localStorage 保存用户的语言偏好
- 下次访问时自动应用上次选择的语言

### 3. **全面覆盖**
所有界面文本都支持国际化，包括：

#### 主界面文本
- 页面标题和副标题
- 上传区域的所有提示文本
- 投篮手选择（左手/右手）
- 投篮方式选择（一段式/二段式）
- 按钮文本（开始分析、上传中、分析中等）

#### 结果展示
- 关键帧标题
- 阶段名称（准备阶段、上升阶段、出手阶段、跟随阶段）
- 完整标注视频标题
- 改进建议标题
- 参考评分标题
- 评级文本（优秀、良好、一般、需改进）

#### 动态消息
- 进度提示（准备中、上传中、分析中等）
- 错误提示（上传失败、分析失败、格式错误等）
- 成功提示

## 💻 技术实现

### 1. **多语言数据结构**
```javascript
const i18n = {
    'zh-CN': {
        title: '🏀 投篮姿势分析器',
        // ... 其他中文文本
    },
    'en-US': {
        title: '🏀 Basketball Shooting Form Analyzer',
        // ... 其他英文文本
    }
};
```

### 2. **自动更新机制**
使用 `data-i18n` 属性标记需要翻译的元素：
```html
<h1 data-i18n="title">🏀 投篮姿势分析器</h1>
<p data-i18n="subtitle">上传你的投篮视频，获取专业的姿势分析和改进建议</p>
```

切换语言时自动遍历所有标记元素并更新文本。

### 3. **翻译函数**
提供 `t(key)` 函数用于动态获取翻译文本：
```javascript
progressText.textContent = t('progress.uploading'); // 自动返回当前语言的文本
```

### 4. **页面加载初始化**
```javascript
document.addEventListener('DOMContentLoaded', () => {
    updateLanguage(); // 自动应用保存的语言设置
});
```

## 📋 支持的语言

### 中文 (zh-CN)
- 简体中文界面
- 专业的篮球术语
- 本地化的表达方式

### 英文 (en-US)
- 标准英文界面
- 专业的篮球术语
- 国际通用表达

## 🎨 UI 设计

### 语言切换按钮样式
- **位置**：右上角固定位置
- **设计**：玻璃态效果 + 渐变边框
- **交互**：悬停时高亮 + 上浮动画
- **图标**：地球图标 🌐 + 语言代码

```css
.lang-btn {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border: 2px solid rgba(255, 255, 255, 0.2);
    padding: 10px 20px;
    border-radius: 12px;
    /* ... 其他样式 */
}

.lang-btn:hover {
    background: rgba(72, 219, 251, 0.2);
    border-color: rgba(72, 219, 251, 0.5);
    transform: translateY(-2px);
    /* ... 其他样式 */
}
```

## 🔧 使用方法

### 用户视角
1. 打开应用，默认显示中文界面
2. 点击右上角的语言按钮（显示 "EN"）
3. 界面立即切换为英文
4. 再次点击按钮（显示 "中文"）切换回中文
5. 语言选择会被自动保存

### 开发者视角

#### 添加新的翻译文本
1. 在 `i18n` 对象中添加对应的键值对：
```javascript
const i18n = {
    'zh-CN': {
        newSection: {
            title: '新板块标题'
        }
    },
    'en-US': {
        newSection: {
            title: 'New Section Title'
        }
    }
};
```

2. 在 HTML 中使用 `data-i18n` 属性：
```html
<h2 data-i18n="newSection.title">新板块标题</h2>
```

3. 或在 JavaScript 中使用 `t()` 函数：
```javascript
element.textContent = t('newSection.title');
```

## 📊 翻译覆盖率

| 类别 | 项目数 | 状态 |
|------|--------|------|
| 界面标题 | 2 | ✅ 100% |
| 上传区域 | 10 | ✅ 100% |
| 结果展示 | 8 | ✅ 100% |
| 动作阶段 | 4 | ✅ 100% |
| 评级等级 | 4 | ✅ 100% |
| 进度消息 | 4 | ✅ 100% |
| 错误消息 | 5 | ✅ 100% |

**总计：37 项 - 100% 翻译完成**

## 🌟 未来扩展

### 潜在新增语言
- 🇯🇵 日语 (ja-JP)
- 🇰🇷 韩语 (ko-KR)
- 🇪🇸 西班牙语 (es-ES)
- 🇫🇷 法语 (fr-FR)

### 扩展方法
只需在 `i18n` 对象中添加新语言的完整翻译，并在 `toggleLanguage()` 函数中添加新语言的切换逻辑即可。

## 🧪 测试建议

### 功能测试
1. ✅ 语言切换按钮可见且可点击
2. ✅ 点击后界面文本立即更新
3. ✅ 刷新页面后保持上次选择的语言
4. ✅ 所有静态文本都正确翻译
5. ✅ 所有动态消息都正确翻译
6. ✅ 错误提示正确显示对应语言

### 兼容性测试
- ✅ Chrome/Edge
- ✅ Safari
- ✅ Firefox
- ✅ 移动端浏览器

## 📝 注意事项

1. **localStorage 依赖**
   - 需要浏览器支持 localStorage
   - 隐私模式可能不保存设置

2. **初次加载**
   - 默认语言为中文
   - 如果 localStorage 中有保存的语言，则使用保存的语言

3. **文本更新**
   - 静态文本通过 `data-i18n` 自动更新
   - 动态文本需要使用 `t()` 函数手动获取

## 🎉 效果展示

### 中文界面
```
🏀 投篮姿势分析器
上传你的投篮视频，获取专业的姿势分析和改进建议

[上传视频]
点击或拖拽视频到这里
支持 MP4, MOV, AVI, WebM
最大 50MB
```

### 英文界面
```
🏀 Basketball Shooting Form Analyzer
Upload your shooting video to get professional form analysis and improvement suggestions

[Upload Video]
Click or drag video here
Supports MP4, MOV, AVI, WebM
Max 50MB
```

---

**更新日期**: 2026-02-16  
**版本**: 1.0.0  
**状态**: ✅ 已完成并测试
