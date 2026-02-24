"""
PDF Export Service
生成分析结果的PDF报告
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage


class PDFExportService:
    """PDF导出服务"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 尝试注册中文字体（如果可用）
        self.font_name = self._register_fonts()
    
    def _register_fonts(self) -> str:
        """
        注册中文字体（可选）
        返回可用的字体名称
        """
        try:
            # 尝试使用系统字体
            font_paths = [
                '/System/Library/Fonts/STHeiti Medium.ttc',  # macOS
                '/System/Library/Fonts/PingFang.ttc',  # macOS
                '/System/Library/Fonts/Hiragino Sans GB.ttc',  # macOS
                'C:/Windows/Fonts/simhei.ttf',  # Windows
                'C:/Windows/Fonts/msyh.ttc',  # Windows 微软雅黑
                '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',  # Linux
            ]
            
            for font_path in font_paths:
                if Path(font_path).exists():
                    try:
                        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                        print(f"成功加载中文字体: {font_path}")
                        return 'ChineseFont'
                    except Exception as e:
                        print(f"尝试加载字体 {font_path} 失败: {e}")
                        continue
        except Exception as e:
            print(f"无法加载中文字体: {e}")
        
        # 如果无法加载中文字体，返回 Helvetica
        print("警告：未找到中文字体，将使用默认字体（可能无法正确显示中文）")
        return 'Helvetica'
    
    def generate_report(
        self,
        task_id: str,
        analysis_result: Dict[str, Any],
        language: str = 'zh-CN'
    ) -> Path:
        """
        生成PDF报告
        
        Args:
            task_id: 任务ID
            analysis_result: 分析结果数据
            language: 语言 ('zh-CN' 或 'en-US')
        
        Returns:
            生成的PDF文件路径
        """
        # PDF文件路径
        pdf_filename = f"report_{task_id}.pdf"
        pdf_path = self.output_dir / pdf_filename
        
        # 创建PDF文档
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # 构建内容
        story = []
        styles = self._get_styles(language)
        
        # 添加标题
        story.extend(self._add_title(styles, language))
        
        # 添加基本信息
        story.extend(self._add_basic_info(analysis_result, styles, language))
        
        # 添加总体评分
        story.extend(self._add_overall_score(analysis_result, styles, language))
        
        # 添加维度评分
        story.extend(self._add_dimension_scores(analysis_result, styles, language))
        
        # 添加关键帧
        story.extend(self._add_key_frames(analysis_result, styles, language))
        
        # 添加改进建议
        story.extend(self._add_suggestions(analysis_result, styles, language))
        
        # 生成PDF
        doc.build(story)
        
        return pdf_path
    
    def _get_styles(self, language: str) -> Dict[str, ParagraphStyle]:
        """获取样式"""
        styles = getSampleStyleSheet()
        
        # 使用已注册的字体
        font_name = self.font_name
        
        custom_styles = {
            'Title': ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=24,
                textColor=colors.HexColor('#1a1f3a'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName=font_name
            ),
            'Heading1': ParagraphStyle(
                'CustomHeading1',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#48dbfb'),
                spaceAfter=12,
                spaceBefore=20,
                fontName=font_name
            ),
            'Heading2': ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#1a1f3a'),
                spaceAfter=10,
                spaceBefore=15,
                fontName=font_name
            ),
            'Body': ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                leading=16,
                spaceAfter=8,
                fontName=font_name
            ),
            'Small': ParagraphStyle(
                'CustomSmall',
                parent=styles['BodyText'],
                fontSize=9,
                textColor=colors.grey,
                fontName=font_name
            )
        }
        
        return custom_styles
    
    def _add_title(self, styles: Dict, language: str) -> List:
        """添加标题"""
        elements = []
        
        title_text = {
            'zh-CN': '投篮姿势分析报告',
            'en-US': 'Basketball Shooting Form Analysis Report'
        }
        
        elements.append(Paragraph(title_text[language], styles['Title']))
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _add_basic_info(self, result: Dict, styles: Dict, language: str) -> List:
        """添加基本信息"""
        elements = []
        
        # 生成时间
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        info_label = {
            'zh-CN': '报告生成时间',
            'en-US': 'Report Generated'
        }
        
        elements.append(
            Paragraph(f"{info_label[language]}: {timestamp}", styles['Small'])
        )
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _add_overall_score(self, result: Dict, styles: Dict, language: str) -> List:
        """添加总体评分"""
        elements = []
        
        title_text = {
            'zh-CN': '总体评分',
            'en-US': 'Overall Score'
        }
        
        rating_map = {
            'zh-CN': {
                'excellent': '优秀',
                'good': '良好',
                'fair': '一般',
                'needs_improvement': '需改进'
            },
            'en-US': {
                'excellent': 'Excellent',
                'good': 'Good',
                'fair': 'Fair',
                'needs_improvement': 'Needs Improvement'
            }
        }
        
        elements.append(Paragraph(title_text[language], styles['Heading1']))
        
        score = result.get('overall_score', 0)
        rating = result.get('rating', 'fair')
        rating_text = rating_map[language].get(rating, rating)
        
        # 创建评分表格样式
        score_number_style = ParagraphStyle(
            'ScoreNumber',
            parent=styles['Body'],
            fontName=self.font_name,
            fontSize=36,
            leading=48,  # 设置行高，确保大字号有足够空间
            textColor=colors.white,
            alignment=TA_CENTER
        )
        
        rating_style = ParagraphStyle(
            'RatingText',
            parent=styles['Body'],
            fontName=self.font_name,
            fontSize=18,
            leading=24,  # 设置行高
            alignment=TA_CENTER
        )
        
        # 创建评分表格（使用 Paragraph 对象）
        score_data = [
            [
                Paragraph(f"{int(score)}", score_number_style),
                Paragraph(rating_text, rating_style)
            ]
        ]
        
        score_table = Table(score_data, colWidths=[2*inch, 3*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#48dbfb')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f0f0f0')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 25),  # 增加内边距
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        elements.append(score_table)
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _add_dimension_scores(self, result: Dict, styles: Dict, language: str) -> List:
        """添加维度评分"""
        elements = []
        
        title_text = {
            'zh-CN': '各维度评分',
            'en-US': 'Dimension Scores'
        }
        
        elements.append(Paragraph(title_text[language], styles['Heading1']))
        
        dimension_scores = result.get('dimension_scores', [])
        
        if dimension_scores:
            # 创建表格数据（使用 Paragraph 对象来支持自动换行）
            header_text = {
                'zh-CN': ['维度', '得分', '反馈'],
                'en-US': ['Dimension', 'Score', 'Feedback']
            }
            
            # 表头样式
            header_style = ParagraphStyle(
                'TableHeader',
                parent=styles['Body'],
                fontName=self.font_name,
                fontSize=11,
                textColor=colors.white,
                alignment=TA_CENTER
            )
            
            # 单元格样式
            cell_style = ParagraphStyle(
                'TableCell',
                parent=styles['Body'],
                fontName=self.font_name,
                fontSize=10,
                leading=14,  # 行高
                alignment=TA_LEFT
            )
            
            # 分数单元格样式
            score_style = ParagraphStyle(
                'ScoreCell',
                parent=styles['Body'],
                fontName=self.font_name,
                fontSize=10,
                alignment=TA_CENTER
            )
            
            # 构建表头
            table_data = [[
                Paragraph(header_text[language][0], header_style),
                Paragraph(header_text[language][1], header_style),
                Paragraph(header_text[language][2], header_style)
            ]]
            
            # 构建数据行（使用 Paragraph 对象）
            for ds in dimension_scores:
                name = ds.get('name', '')
                score = int(ds.get('score', 0))
                feedback = ds.get('feedback', '')
                
                table_data.append([
                    Paragraph(name, cell_style),
                    Paragraph(str(score), score_style),
                    Paragraph(feedback, cell_style)
                ])
            
            # 创建表格（不固定行高，让内容自动决定）
            table = Table(table_data, colWidths=[1.8*inch, 0.8*inch, 3.9*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#48dbfb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ]))
            
            elements.append(table)
        
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _add_key_frames(self, result: Dict, styles: Dict, language: str) -> List:
        """添加关键帧"""
        elements = []
        
        title_text = {
            'zh-CN': '动作关键帧',
            'en-US': 'Key Frames'
        }
        
        phase_names = {
            'zh-CN': {
                'preparation': '准备阶段',
                'lifting': '上升阶段',
                'release': '出手阶段',
                'follow_through': '跟随阶段'
            },
            'en-US': {
                'preparation': 'Preparation',
                'lifting': 'Lifting',
                'release': 'Release',
                'follow_through': 'Follow Through'
            }
        }
        
        elements.append(Paragraph(title_text[language], styles['Heading1']))
        
        key_frames = result.get('key_frames', [])
        
        if key_frames:
            # 一行一张图，让图片更大更清晰
            for kf in key_frames:
                image_url = kf.get('image_url', '')
                phase = kf.get('phase', '')
                phase_name = phase_names[language].get(phase, phase)
                
                # 从URL获取本地文件路径
                if image_url.startswith('/results/'):
                    image_path = self.output_dir.parent / image_url.lstrip('/')
                else:
                    continue
                
                if image_path.exists():
                    try:
                        # 打开图片获取原始尺寸
                        img = PILImage.open(image_path)
                        original_width, original_height = img.size
                        aspect_ratio = original_width / original_height
                        
                        # 设置最大宽度（A4页面可用宽度约6.5英寸）
                        max_width = 6.5 * inch
                        max_height = 8 * inch  # 最大高度限制
                        
                        # 根据宽高比计算显示尺寸
                        if aspect_ratio > 1:  # 横图
                            display_width = max_width
                            display_height = max_width / aspect_ratio
                            # 如果高度超过限制，从高度反推宽度
                            if display_height > max_height:
                                display_height = max_height
                                display_width = max_height * aspect_ratio
                        else:  # 竖图
                            display_height = min(max_height, max_width / aspect_ratio)
                            display_width = display_height * aspect_ratio
                        
                        # 转换为reportlab Image（保持原始宽高比）
                        img_buffer = io.BytesIO()
                        img.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        
                        rl_img = Image(img_buffer, width=display_width, height=display_height)
                        
                        # 阶段名称样式
                        phase_style = ParagraphStyle(
                            'PhaseLabel',
                            parent=styles['Body'],
                            fontName=self.font_name,
                            fontSize=12,
                            alignment=TA_CENTER,
                            textColor=colors.HexColor('#0984e3'),
                            spaceAfter=10
                        )
                        
                        # 添加阶段标题
                        elements.append(Paragraph(f"<b>{phase_name}</b>", phase_style))
                        
                        # 创建单张图片的表格（用于居中，宽度适应图片）
                        table_width = display_width + 0.2*inch  # 留一点边距
                        img_table = Table([[rl_img]], colWidths=[table_width])
                        img_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
                            ('PADDING', (0, 0), (0, 0), 10),
                            ('BOX', (0, 0), (0, 0), 1, colors.grey)
                        ]))
                        
                        elements.append(img_table)
                        elements.append(Spacer(1, 0.3*inch))
                    except Exception as e:
                        print(f"无法加载图片 {image_path}: {e}")
        
        elements.append(PageBreak())
        
        return elements
    
    def _add_suggestions(self, result: Dict, styles: Dict, language: str) -> List:
        """添加改进建议"""
        elements = []
        
        title_text = {
            'zh-CN': '改进建议',
            'en-US': 'Improvement Suggestions'
        }
        
        no_issues_text = {
            'zh-CN': '未发现明显问题，投篮姿势很好！',
            'en-US': 'No obvious issues found, great shooting form!'
        }
        
        severity_map = {
            'zh-CN': {
                'high': '高优先级',
                'medium': '中优先级',
                'low': '低优先级'
            },
            'en-US': {
                'high': 'High Priority',
                'medium': 'Medium Priority',
                'low': 'Low Priority'
            }
        }
        
        elements.append(Paragraph(title_text[language], styles['Heading1']))
        
        issues = result.get('issues', [])
        
        if issues:
            for idx, issue in enumerate(issues, 1):
                severity = issue.get('severity', 'medium')
                severity_text = severity_map[language].get(severity, severity)
                description = issue.get('description', '')
                suggestion = issue.get('suggestion', '')
                
                # 问题标题
                issue_title = f"{idx}. [{severity_text}] {description}"
                elements.append(Paragraph(issue_title, styles['Heading2']))
                
                # 建议内容
                elements.append(Paragraph(f"💡 {suggestion}", styles['Body']))
                elements.append(Spacer(1, 0.15*inch))
        else:
            elements.append(Paragraph(no_issues_text[language], styles['Body']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _add_footer(self, styles: Dict, language: str) -> List:
        """添加页脚"""
        elements = []
        
        footer_text = {
            'zh-CN': '* 本报告由AI系统自动生成，建议结合实际情况和专业教练指导使用。',
            'en-US': '* This report is automatically generated by AI. Please use it in conjunction with professional coaching.'
        }
        
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(footer_text[language], styles['Small']))
        
        return elements
