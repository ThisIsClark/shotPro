"""
Template Model
投篮模板数据模型
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
import json


@dataclass
class TemplateKeyFrame:
    """模板关键帧"""
    phase: str  # preparation, lifting, release, follow_through
    frame_number: int
    timestamp: float
    image_path: str  # 相对于templates目录的路径
    angles: Optional[Dict[str, float]] = None


@dataclass
class Template:
    """投篮模板"""
    id: str  # 唯一标识（使用timestamp或UUID）
    name: str  # 模板名称（如"Curry"）
    description: str = ""
    created_at: str = ""
    key_frames: List[TemplateKeyFrame] = None
    video_info: Optional[Dict] = None  # 原视频信息
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.key_frames is None:
            self.key_frames = []
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at,
            'key_frames': [
                {
                    'phase': kf.phase,
                    'frame_number': kf.frame_number,
                    'timestamp': kf.timestamp,
                    'image_path': kf.image_path,
                    'angles': kf.angles
                }
                for kf in self.key_frames
            ],
            'video_info': self.video_info
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Template':
        """从字典创建"""
        key_frames = [
            TemplateKeyFrame(
                phase=kf['phase'],
                frame_number=kf['frame_number'],
                timestamp=kf['timestamp'],
                image_path=kf['image_path'],
                angles=kf.get('angles')
            )
            for kf in data.get('key_frames', [])
        ]
        
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            created_at=data.get('created_at', ''),
            key_frames=key_frames,
            video_info=data.get('video_info')
        )


class TemplateManager:
    """模板管理器"""
    
    def __init__(self, templates_dir: Path):
        """
        初始化模板管理器
        
        Args:
            templates_dir: 模板存储目录
        """
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.templates_dir / "index.json"
        self._ensure_index()
    
    def _ensure_index(self):
        """确保索引文件存在"""
        if not self.index_file.exists():
            self._save_index({})
    
    def _load_index(self) -> Dict:
        """加载索引"""
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载模板索引失败: {e}")
            return {}
    
    def _save_index(self, index: Dict):
        """保存索引"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    def create_template(
        self,
        template_id: str,
        name: str,
        key_frames: List[TemplateKeyFrame],
        description: str = "",
        video_info: Optional[Dict] = None
    ) -> Template:
        """
        创建模板
        
        Args:
            template_id: 模板ID
            name: 模板名称
            key_frames: 关键帧列表
            description: 描述
            video_info: 视频信息
        
        Returns:
            创建的模板
        """
        template = Template(
            id=template_id,
            name=name,
            description=description,
            key_frames=key_frames,
            video_info=video_info
        )
        
        # 创建模板目录
        template_dir = self.templates_dir / template_id
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存模板元数据
        metadata_file = template_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(template.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 更新索引
        index = self._load_index()
        index[template_id] = {
            'name': name,
            'description': description,
            'created_at': template.created_at,
            'key_frame_count': len(key_frames)
        }
        self._save_index(index)
        
        return template
    
    def get_template(self, template_id: str) -> Optional[Template]:
        """
        获取模板
        
        Args:
            template_id: 模板ID
        
        Returns:
            模板对象或None
        """
        template_dir = self.templates_dir / template_id
        metadata_file = template_dir / "metadata.json"
        
        if not metadata_file.exists():
            print(f"[DEBUG 模板加载] metadata.json 不存在: {metadata_file}")
            return None
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"[DEBUG 模板加载] 从 metadata.json 读取的数据:")
            print(f"  - name: {data.get('name')}")
            print(f"  - key_frames 数量: {len(data.get('key_frames', []))}")
            
            template = Template.from_dict(data)
            print(f"[DEBUG 模板加载] 创建的 Template 对象, key_frames 数量: {len(template.key_frames)}")
            
            return template
        except Exception as e:
            print(f"加载模板失败 {template_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def list_templates(self) -> List[Dict]:
        """
        列出所有模板
        
        Returns:
            模板列表
        """
        index = self._load_index()
        templates = []
        
        for template_id, info in index.items():
            templates.append({
                'id': template_id,
                'name': info['name'],
                'description': info.get('description', ''),
                'created_at': info['created_at'],
                'key_frame_count': info.get('key_frame_count', 0)
            })
        
        # 按创建时间倒序排列
        templates.sort(key=lambda x: x['created_at'], reverse=True)
        return templates
    
    def delete_template(self, template_id: str) -> bool:
        """
        删除模板
        
        Args:
            template_id: 模板ID
        
        Returns:
            是否删除成功
        """
        template_dir = self.templates_dir / template_id
        
        if not template_dir.exists():
            return False
        
        try:
            # 删除模板目录和所有文件
            import shutil
            shutil.rmtree(template_dir)
            
            # 更新索引
            index = self._load_index()
            if template_id in index:
                del index[template_id]
                self._save_index(index)
            
            return True
        except Exception as e:
            print(f"删除模板失败 {template_id}: {e}")
            return False
    
    def get_template_dir(self, template_id: str) -> Path:
        """获取模板目录路径"""
        return self.templates_dir / template_id
