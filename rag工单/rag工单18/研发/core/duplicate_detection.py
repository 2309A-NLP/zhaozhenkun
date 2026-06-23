"""
重复检测模块
Duplicate Detection Module
"""

import os
import hashlib
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from .base import ConfigManager, logger

try:
    from simhash import Simhash, SimhashIndex
    SIMHASH_AVAILABLE = True
except ImportError:
    SIMHASH_AVAILABLE = False
    logger.warning("simhash未安装，SimHash相似度检测将不可用。请运行: pip install simhash")


class DuplicateDetector:
    """重复检测器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.enable_md5 = config.get('duplicate_detection.enable_md5', True)
        self.enable_simhash = config.get('duplicate_detection.enable_simhash', False)
        self.simhash_similarity_threshold = config.get('duplicate_detection.simhash_similarity_threshold', 0.85)
        self.simhash_hamming_distance = config.get('duplicate_detection.simhash_hamming_distance', 3)
        self.max_pending_conflicts = config.get('duplicate_detection.max_pending_conflicts', 50)
    
    def detect_duplicates(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        检测重复文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            重复检测结果
        """
        if not file_paths:
            logger.warning("没有文件需要检测")
            return self._get_empty_result()
        
        # MD5精确重复检测
        md5_results = self._detect_md5_duplicates(file_paths) if self.enable_md5 else {}
        
        # SimHash相似度检测
        simhash_results = self._detect_simhash_duplicates(file_paths) if self.enable_simhash else {}
        
        # 合并结果
        all_duplicates = []
        pending_conflicts = []
        
        # 处理MD5重复
        if md5_results:
            for md5_hash, files in md5_results.items():
                if len(files) > 1:
                    duplicate_group = {
                        'type': 'exact',
                        'hash': md5_hash,
                        'files': files,
                        'count': len(files)
                    }
                    all_duplicates.append(duplicate_group)
        
        # 处理SimHash相似
        if simhash_results:
            for simhash_pair in simhash_results:
                pending_conflicts.append({
                    'type': 'similar',
                    'file1': simhash_pair[0],
                    'file2': simhash_pair[1],
                    'similarity': simhash_pair[2],
                    'needs_confirmation': True
                })
        
        # 限制待确认列表数量
        if len(pending_conflicts) > self.max_pending_conflicts:
            pending_conflicts = pending_conflicts[:self.max_pending_conflicts]
        
        # 统计重复文件数量
        duplicate_file_count = 0
        for group in all_duplicates:
            duplicate_file_count += group['count'] - 1  # 每组只保留一个，其余为重复
        
        result = {
            'total_files': len(file_paths),
            'md5_duplicates': all_duplicates,
            'simhash_similar': pending_conflicts,
            'duplicate_file_count': duplicate_file_count,
            'pending_conflict_count': len(pending_conflicts),
            'duplicate_groups': len(all_duplicates)
        }
        
        logger.info(f"重复检测完成: {len(all_duplicates)} 个重复组，{len(pending_conflicts)} 个待确认冲突")
        return result
    
    def _detect_md5_duplicates(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """检测MD5精确重复"""
        md5_dict = defaultdict(list)
        
        for file_path in file_paths:
            try:
                md5_hash = self._calculate_md5(file_path)
                if md5_hash:
                    md5_dict[md5_hash].append(file_path)
            except Exception as e:
                logger.warning(f"计算MD5时出错: {file_path}, 错误: {e}")
                continue
        
        # 只返回有重复的组
        return {k: v for k, v in md5_dict.items() if len(v) > 1}
    
    def _calculate_md5(self, file_path: str) -> str:
        """计算文件MD5哈希"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"计算MD5失败: {file_path}, 错误: {e}")
            return ""
    
    def _detect_simhash_duplicates(self, file_paths: List[str]) -> List[Tuple[str, str, float]]:
        """检测SimHash相似度"""
        if not SIMHASH_AVAILABLE:
            logger.warning("simhash未安装，跳过SimHash检测")
            return []
        
        # 计算每个文件的SimHash
        simhash_data = []
        for file_path in file_paths:
            try:
                content = self._read_file_content(file_path)
                if content:
                    simhash_value = Simhash(content)
                    simhash_data.append((file_path, simhash_value))
            except Exception as e:
                logger.warning(f"计算SimHash时出错: {file_path}, 错误: {e}")
                continue
        
        # 查找相似文件对
        similar_pairs = []
        
        # 创建SimhashIndex用于快速查找
        if len(simhash_data) > 1:
            try:
                # 将数据转换为SimhashIndex需要的格式
                hashes = [(str(i), simhash_value) for i, (_, simhash_value) in enumerate(simhash_data)]
                index = SimhashIndex(hashes, k=self.simhash_hamming_distance)
                
                # 查找每个文件的相似文件
                for i, (file_path, simhash_value) in enumerate(simhash_data):
                    # 查找相似的SimHash
                    similar_indices = index.get_near_dups(simhash_value)
                    
                    for j_str in similar_indices:
                        j = int(j_str)
                        if j > i:  # 避免重复检测
                            # 计算相似度
                            hamming_distance = simhash_value.distance(simhash_data[j][1])
                            similarity = 1 - (hamming_distance / 64)  # SimHash是64位
                            
                            if similarity >= self.simhash_similarity_threshold:
                                similar_pairs.append((
                                    file_path,
                                    simhash_data[j][0],
                                    round(similarity, 4)
                                ))
            except Exception as e:
                logger.warning(f"SimHash索引创建失败: {e}")
                # 回退到暴力搜索
                similar_pairs = self._brute_force_simhash_search(simhash_data)
        
        return similar_pairs
    
    def _brute_force_simhash_search(self, simhash_data: List[Tuple[str, 'Simhash']]) -> List[Tuple[str, str, float]]:
        """暴力搜索SimHash相似文件"""
        similar_pairs = []
        n = len(simhash_data)
        
        for i in range(n):
            for j in range(i + 1, n):
                try:
                    hamming_distance = simhash_data[i][1].distance(simhash_data[j][1])
                    similarity = 1 - (hamming_distance / 64)
                    
                    if similarity >= self.simhash_similarity_threshold:
                        similar_pairs.append((
                            simhash_data[i][0],
                            simhash_data[j][0],
                            round(similarity, 4)
                        ))
                except Exception as e:
                    logger.warning(f"计算SimHash距离时出错: {simhash_data[i][0]} vs {simhash_data[j][0]}, 错误: {e}")
                    continue
        
        return similar_pairs
    
    def _read_file_content(self, file_path: str) -> str:
        """读取文件内容用于SimHash计算"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 对于文本文件，直接读取
            if file_ext in ['.txt', '.md', '.html', '.htm', '.rtf']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            
            # 对于PDF文件
            elif file_ext == '.pdf':
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        text_parts = []
                        for page in pdf.pages:
                            text = page.extract_text() or ""
                            text_parts.append(text)
                        return " ".join(text_parts)
                except ImportError:
                    return ""
            
            # 对于Word文档
            elif file_ext in ['.docx', '.doc']:
                try:
                    from docx import Document
                    doc = Document(file_path)
                    text_parts = []
                    for para in doc.paragraphs:
                        text_parts.append(para.text)
                    return " ".join(text_parts)
                except ImportError:
                    return ""
            
            else:
                return ""
                
        except Exception as e:
            logger.error(f"读取文件内容时出错: {file_path}, 错误: {e}")
            return ""
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """获取空结果"""
        return {
            'total_files': 0,
            'md5_duplicates': [],
            'simhash_similar': [],
            'duplicate_file_count': 0,
            'pending_conflict_count': 0,
            'duplicate_groups': 0
        }
    
    def get_duplicate_summary(self, detection_result: Dict[str, Any]) -> str:
        """获取重复检测摘要"""
        if not detection_result or detection_result['total_files'] == 0:
            return "没有文件需要检测"
        
        summary_lines = [
            f"重复检测结果摘要:",
            f"总文件数: {detection_result['total_files']}",
            "",
            "MD5精确重复:",
            f"  重复组数: {detection_result['duplicate_groups']}",
            f"  重复文件数: {detection_result['duplicate_file_count']}",
        ]
        
        if detection_result['md5_duplicates']:
            summary_lines.append("\n重复文件详情:")
            for i, group in enumerate(detection_result['md5_duplicates'][:5], 1):
                summary_lines.append(f"  组 {i}: {group['count']} 个文件")
                for file_path in group['files'][:3]:  # 只显示前3个
                    summary_lines.append(f"    - {os.path.basename(file_path)}")
                if group['count'] > 3:
                    summary_lines.append(f"    ... 还有 {group['count'] - 3} 个文件")
        
        if detection_result['pending_conflict_count'] > 0:
            summary_lines.append(f"\nSimHash相似文件: {detection_result['pending_conflict_count']} 对")
            summary_lines.append("（需要人工确认的相似文件已添加到待确认列表）")
        
        return "\n".join(summary_lines)