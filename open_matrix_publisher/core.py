import os, sys, json, time

class MatrixPublisherEngine:
    """
    Open Matrix Publisher (全域矩阵) 核心调度器
    内置防重幂等账本、凭证 Vault 校验与 Playwright/SAU 双引擎驱动
    """
    def __init__(self, workspace_path=None):
        self.workspace = workspace_path or os.getcwd()
        self.history_file = os.path.join(self.workspace, "dispatch_history.json")
        
    def load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"records": [], "last_dispatch": {}}

    def is_published(self, video_path, platform_id):
        history = self.load_history()
        video_name = os.path.basename(video_path)
        for rec in history.get("records", []):
            if rec.get("video_file") == video_name:
                p_info = rec.get("platforms", {}).get(platform_id, {})
                if p_info.get("status") == "success":
                    return True
        return False

    def get_summary(self):
        history = self.load_history()
        summary = {}
        for rec in history.get("records", []):
            v_name = rec.get("video_file")
            summary[v_name] = {}
            for p, d in rec.get("platforms", {}).items():
                summary[v_name][p] = d.get("status")
        return summary
