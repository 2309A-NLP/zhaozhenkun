"""
文档质量评估API模块
Document Quality Assessment API Module
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

from ..core.assessor import DocumentQualityAssessor
from ..core.base import ConfigManager, logger

# 创建Flask应用
app = Flask(__name__)

# 配置
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['REPORT_FOLDER'] = './reports'

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

# 全局评估器实例
assessor = None


def init_assessor(config_path: str = None):
    """初始化评估器"""
    global assessor
    assessor = DocumentQualityAssessor(config_path)
    logger.info("API评估器初始化完成")


@app.route('/v1/document/quality-inspection', methods=['POST'])
def quality_inspection():
    """
    文档质量检查API端点
    
    请求体:
    {
        "folder_path": "/path/to/documents",  # 文件夹路径
        "file_list": ["/path/to/file1.pdf", "/path/to/file2.docx"],  # 或文件列表
        "output_formats": ["json", "html"],  # 输出格式
        "config_overrides": {}  # 配置覆盖
    }
    
    返回:
    {
        "success": true,
        "data": {
            "assessment_result": {...},
            "report_files": {...}
        },
        "message": "评估完成"
    }
    """
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据为空',
                'error': 'No JSON data provided'
            }), 400
        
        # 获取参数
        folder_path = data.get('folder_path')
        file_list = data.get('file_list')
        output_formats = data.get('output_formats', ['json', 'html'])
        config_overrides = data.get('config_overrides', {})
        
        # 验证参数
        if not folder_path and not file_list:
            return jsonify({
                'success': False,
                'message': '必须提供folder_path或file_list参数',
                'error': 'Missing required parameters'
            }), 400
        
        # 初始化评估器（如果需要）
        if assessor is None:
            init_assessor()
        
        # 应用配置覆盖
        if config_overrides:
            _apply_config_overrides(config_overrides)
        
        # 执行评估
        if folder_path:
            # 评估文件夹
            if not os.path.exists(folder_path):
                return jsonify({
                    'success': False,
                    'message': f'文件夹不存在: {folder_path}',
                    'error': 'Folder not found'
                }), 404
            
            assessment_result = assessor.assess_directory(folder_path)
        else:
            # 评估文件列表
            assessment_result = assessor.assess_files(file_list)
        
        # 生成报告
        report_files = {}
        if output_formats:
            report_files = assessor.generate_report(
                assessment_result,
                output_dir=app.config['REPORT_FOLDER'],
                formats=output_formats
            )
        
        # 返回结果
        response_data = {
            'assessment_result': assessment_result,
            'report_files': report_files
        }
        
        return jsonify({
            'success': True,
            'data': response_data,
            'message': '评估完成'
        })
        
    except Exception as e:
        logger.error(f"质量检查API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'评估过程中发生错误: {str(e)}',
            'error': str(e)
        }), 500


@app.route('/v1/document/quality-inspection/upload', methods=['POST'])
def quality_inspection_upload():
    """
    文档质量检查API端点（文件上传版本）
    
    请求: multipart/form-data
    - files: 上传的文件
    - config: 配置JSON字符串（可选）
    
    返回:
    {
        "success": true,
        "data": {
            "assessment_result": {...},
            "report_files": {...}
        },
        "message": "评估完成"
    }
    """
    try:
        # 检查是否有文件上传
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有上传文件',
                'error': 'No files uploaded'
            }), 400
        
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({
                'success': False,
                'message': '没有选择文件',
                'error': 'No files selected'
            }), 400
        
        # 获取配置
        config_json = request.form.get('config', '{}')
        try:
            config_data = json.loads(config_json)
        except json.JSONDecodeError:
            config_data = {}
        
        # 保存上传的文件
        uploaded_files = []
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                uploaded_files.append(file_path)
        
        if not uploaded_files:
            return jsonify({
                'success': False,
                'message': '没有有效的文件',
                'error': 'No valid files'
            }), 400
        
        # 初始化评估器
        if assessor is None:
            init_assessor()
        
        # 应用配置覆盖
        if config_data:
            _apply_config_overrides(config_data)
        
        # 执行评估
        assessment_result = assessor.assess_files(uploaded_files)
        
        # 生成报告
        output_formats = config_data.get('output_formats', ['json', 'html'])
        report_files = assessor.generate_report(
            assessment_result,
            output_dir=app.config['REPORT_FOLDER'],
            formats=output_formats
        )
        
        # 清理上传的文件
        for file_path in uploaded_files:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"清理上传文件失败: {file_path}, 错误: {e}")
        
        # 返回结果
        response_data = {
            'assessment_result': assessment_result,
            'report_files': report_files
        }
        
        return jsonify({
            'success': True,
            'data': response_data,
            'message': '评估完成'
        })
        
    except Exception as e:
        logger.error(f"质量检查上传API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'评估过程中发生错误: {str(e)}',
            'error': str(e)
        }), 500


@app.route('/v1/document/quality-inspection/report/<filename>', methods=['GET'])
def download_report(filename):
    """
    下载评估报告
    
    路径参数:
    - filename: 报告文件名
    
    返回: 报告文件
    """
    try:
        # 安全检查
        filename = secure_filename(filename)
        file_path = os.path.join(app.config['REPORT_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': f'报告文件不存在: {filename}',
                'error': 'Report file not found'
            }), 404
        
        # 发送文件
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"下载报告错误: {e}")
        return jsonify({
            'success': False,
            'message': f'下载报告失败: {str(e)}',
            'error': str(e)
        }), 500


@app.route('/v1/document/quality-inspection/health', methods=['GET'])
def health_check():
    """
    健康检查端点
    
    返回:
    {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00",
        "version": "1.0.0"
    }
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'assessor_initialized': assessor is not None
    })


@app.route('/v1/document/quality-inspection/config', methods=['GET'])
def get_config():
    """
    获取当前配置
    
    返回:
    {
        "success": true,
        "data": {
            "config": {...}
        }
    }
    """
    try:
        if assessor is None:
            init_assessor()
        
        return jsonify({
            'success': True,
            'data': {
                'config': assessor.config.config
            }
        })
        
    except Exception as e:
        logger.error(f"获取配置错误: {e}")
        return jsonify({
            'success': False,
            'message': f'获取配置失败: {str(e)}',
            'error': str(e)
        }), 500


@app.route('/v1/document/quality-inspection/config', methods=['PUT'])
def update_config():
    """
    更新配置
    
    请求体:
    {
        "config": {...}
    }
    
    返回:
    {
        "success": true,
        "message": "配置更新成功"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'config' not in data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误',
                'error': 'Invalid request data'
            }), 400
        
        config_data = data['config']
        
        if assessor is None:
            init_assessor()
        
        # 更新配置
        assessor.config.config.update(config_data)
        
        return jsonify({
            'success': True,
            'message': '配置更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新配置错误: {e}")
        return jsonify({
            'success': False,
            'message': f'更新配置失败: {str(e)}',
            'error': str(e)
        }), 500


def _apply_config_overrides(config_overrides: Dict[str, Any]):
    """应用配置覆盖"""
    if not assessor:
        return
    
    for key, value in config_overrides.items():
        # 支持点分路径
        keys = key.split('.')
        config = assessor.config.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value


def create_app(config_path: str = None) -> Flask:
    """
    创建Flask应用
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Flask应用实例
    """
    init_assessor(config_path)
    return app


def run_api(host: str = '0.0.0.0', port: int = 5000, debug: bool = False, config_path: str = None):
    """
    运行API服务
    
    Args:
        host: 主机地址
        port: 端口号
        debug: 调试模式
        config_path: 配置文件路径
    """
    init_assessor(config_path)
    
    logger.info(f"启动API服务: {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    # 直接运行
    run_api(debug=True)