# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：版本与协同路由 - 版本管理、协同会话与WebSocket广播

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from auth import auth_service
from schemas import CompareRequest, CreateCollaborationSessionRequest
from version_control import version_control_service, collaboration_manager
from app_state import get_generated_content_or_404, save_generated_content, collaboration_connections

router = APIRouter()


@router.get("/api/v1/version/versions/{content_id}", tags=["版本管理"], summary="获取内容版本列表")
@router.get("/api/v1/version/content/{content_id}/versions", tags=["版本管理"], summary="获取内容版本列表")
async def get_versions(content_id: str,
                       current_user: dict = Depends(auth_service.get_current_user)):
    """获取版本列表 - 返回指定内容的所有历史版本"""
    versions = version_control_service.get_versions(content_id)
    return {"code": 200, "data": {"content_id": content_id, "versions": versions, "total": len(versions)}}


@router.get("/api/v1/version/{version_id}", tags=["版本管理"], summary="获取指定版本快照")
async def get_version_detail(version_id: str,
                             current_user: dict = Depends(auth_service.get_current_user)):
    """获取版本详情 - 返回完整版本快照"""
    version = version_control_service.get_version_detail(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    return {"code": 200, "data": version}


@router.post("/api/v1/version/content/{content_id}/restore/{version_id}", tags=["版本管理"], summary="恢复历史版本")
async def restore_version(content_id: str, version_id: str,
                          current_user: dict = Depends(auth_service.get_current_user)):
    """恢复历史版本 - 用历史快照覆盖当前内容并生成新版本"""
    restored = version_control_service.restore_version(content_id, version_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    content = get_generated_content_or_404(content_id)
    content["raw_content"] = restored
    content["updated_at"] = datetime.now().isoformat()
    save_generated_content(content)
    version = version_control_service.save_version(
        content_id=content_id,
        content_snapshot=restored,
        editor_id=current_user["user_id"],
        change_summary=f"恢复版本 {version_id}",
    )
    return {"code": 200, "message": "版本恢复成功", "data": {"content_id": content_id, "restored_from_version": version_id, "version": version}}


@router.post("/api/v1/version/compare", tags=["版本管理"], summary="对比版本差异")
async def compare_versions(req: CompareRequest,
                           current_user: dict = Depends(auth_service.get_current_user)):
    """对比版本差异 - 返回两个版本之间的文本差异"""
    diff = version_control_service.compare_versions(req.version_id_a, req.version_id_b)
    if not diff:
        raise HTTPException(status_code=404, detail="版本不存在")
    return {"code": 200, "data": diff}


@router.post("/api/v1/collaboration/session/create", tags=["协同编辑"], summary="创建协同编辑会话")
async def create_collaboration_session(req: CreateCollaborationSessionRequest,
                                       current_user: dict = Depends(auth_service.get_current_user)):
    """创建协同编辑会话 - 返回新的会话ID"""
    get_generated_content_or_404(req.content_id)
    session = collaboration_manager.create_session(req.content_id, current_user["user_id"])
    return {"code": 200, "data": session}


@router.post("/api/v1/collaboration/session/{session_id}/join", tags=["协同编辑"], summary="加入会话")
async def join_collaboration_session(session_id: str,
                                     current_user: dict = Depends(auth_service.get_current_user)):
    """加入协同编辑会话"""
    success = collaboration_manager.join_session(session_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在或已失效")
    return {"code": 200, "message": "加入会话成功", "data": collaboration_manager.get_session_info(session_id)}


@router.post("/api/v1/collaboration/session/{session_id}/leave", tags=["协同编辑"], summary="离开会话")
async def leave_collaboration_session(session_id: str,
                                      current_user: dict = Depends(auth_service.get_current_user)):
    """离开协同编辑会话"""
    success = collaboration_manager.leave_session(session_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"code": 200, "message": "离开会话成功", "data": {"session_id": session_id}}


@router.get("/api/v1/collaboration/session/{session_id}/participants", tags=["协同编辑"], summary="获取参与者列表")
async def get_collaboration_participants(session_id: str,
                                         current_user: dict = Depends(auth_service.get_current_user)):
    """获取参与者列表"""
    session = collaboration_manager.get_session_info(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"code": 200, "data": {"session_id": session_id, "participants": session.get("participants", [])}}


@router.websocket("/ws/collaboration/{content_id}")
async def collaboration_websocket(websocket: WebSocket, content_id: str):
    """协同编辑WebSocket - 支持多人实时协作编辑"""
    await websocket.accept()
    user_id = f"user_{id(websocket)}"
    session_id = None
    room = collaboration_connections.setdefault(content_id, set())
    room.add(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")
            if action == "join":
                session = collaboration_manager.create_session(content_id, user_id)
                session_id = session["session_id"]
                await websocket.send_json({"action": "joined", "session_id": session_id, "participants": session["participants"]})
            elif action == "edit" and session_id:
                payload = {"action": "update", "user_id": user_id, "delta": data.get("delta", ""), "timestamp": datetime.now().isoformat()}
                disconnected = []
                for connection in list(room):
                    try:
                        await connection.send_json(payload)
                    except Exception:
                        disconnected.append(connection)
                for connection in disconnected:
                    room.discard(connection)
            elif action == "leave":
                if session_id:
                    collaboration_manager.leave_session(session_id, user_id)
                break
            elif action == "ping":
                await websocket.send_json({"action": "pong"})
    except WebSocketDisconnect:
        if session_id:
            collaboration_manager.leave_session(session_id, user_id)
    finally:
        room.discard(websocket)
        if not room:
            collaboration_connections.pop(content_id, None)
