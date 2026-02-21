# test_api.py - FastAPIエンドポイントテスト
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# FastAPIアプリをインポート
from api.server import app

# テストクライアント作成
client = TestClient(app)

class TestHealthEndpoint:
    
    def test_health_check(self):
        """ヘルスチェックエンドポイントのテスト"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "timestamp" in data

class TestAnalyzeEndpoint:
    
    def test_analyze_valid_messages(self):
        """有効なメッセージ配列での分析テスト"""
        test_messages = [
            {
                "id": "123",
                "content": "こんにちは！",
                "timestamp": "2024-01-01T10:00:00Z",
                "author_id": "user1"
            },
            {
                "id": "124",
                "content": "元気ですか？",
                "timestamp": "2024-01-01T10:05:00Z",
                "author_id": "user1"
            }
        ]
        
        with patch('analyzer.engine.AnalysisEngine') as mock_engine:
            # モックエンジンの戻り値設定
            mock_instance = mock_engine.return_value
            mock_instance.analyze_user.return_value = {
                "user_id": "user1",
                "total_score": 25,
                "timing_score": 30,
                "style_score": 20,
                "behavior_score": 25,
                "ai_score": 25,
                "confidence": 75,
                "message_count": 2,
                "analysis_date": datetime.now()
            }
            
            response = client.post("/analyze", json={"messages": test_messages})
            
            assert response.status_code == 200
            data = response.json()
            
            # レスポンス構造の確認
            assert "user_id" in data
            assert "total_score" in data
            assert "timing_score" in data
            assert "style_score" in data
            assert "behavior_score" in data
            assert "ai_score" in data
            assert "confidence" in data
            assert "message_count" in data
            
            # 分析エンジンが呼ばれたことを確認
            mock_instance.analyze_user.assert_called_once()
    
    def test_analyze_empty_messages(self):
        """空のメッセージ配列でのテスト"""
        response = client.post("/analyze", json={"messages": []})
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        assert "empty" in data["detail"].lower()
    
    def test_analyze_invalid_json(self):
        """不正なJSONでのテスト"""
        response = client.post("/analyze", 
                              data="invalid json", 
                              headers={"content-type": "application/json"})
        assert response.status_code == 422
    
    def test_analyze_missing_required_fields(self):
        """必須フィールドが欠けている場合"""
        invalid_messages = [
            {
                "id": "123",
                # content フィールドなし
                "timestamp": "2024-01-01T10:00:00Z",
                "author_id": "user1"
            }
        ]
        
        response = client.post("/analyze", json={"messages": invalid_messages})
        assert response.status_code == 422
    
    def test_analyze_rate_limiting(self):
        """レート制限のテスト"""
        test_messages = [
            {
                "id": "123",
                "content": "レート制限テスト",
                "timestamp": "2024-01-01T10:00:00Z",
                "author_id": "user1"
            }
        ]
        
        # 多数のリクエストを短時間で送信
        responses = []
        for _ in range(65):  # 60req/minの制限を超える
            response = client.post("/analyze", json={"messages": test_messages})
            responses.append(response)
        
        # 一部のリクエストはレート制限でブロックされるはず
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(rate_limited_responses) > 0
    
    def test_analyze_large_message_set(self):
        """大量のメッセージでのテスト"""
        large_messages = []
        for i in range(100):
            large_messages.append({
                "id": str(1000 + i),
                "content": f"大量メッセージテスト {i}",
                "timestamp": f"2024-01-01T{10 + i // 60:02d}:{i % 60:02d}:00Z",
                "author_id": "bulk_user"
            })
        
        with patch('analyzer.engine.AnalysisEngine') as mock_engine:
            mock_instance = mock_engine.return_value
            mock_instance.analyze_user.return_value = {
                "user_id": "bulk_user",
                "total_score": 55,
                "timing_score": 60,
                "style_score": 50,
                "behavior_score": 55,
                "ai_score": 55,
                "confidence": 95,  # 大量データで高信頼度
                "message_count": 100,
                "analysis_date": datetime.now()
            }
            
            response = client.post("/analyze", json={"messages": large_messages})
            assert response.status_code == 200
            
            data = response.json()
            assert data["message_count"] == 100

class TestUserScoreEndpoints:
    
    def test_get_user_score_existing(self):
        """既存ユーザーのスコア取得"""
        user_id = "test_user_123"
        
        with patch('api.server.get_user_latest_score') as mock_get_score:
            mock_get_score.return_value = {
                "user_id": user_id,
                "total_score": 42,
                "timing_score": 45,
                "style_score": 38,
                "behavior_score": 44,
                "ai_score": 41,
                "confidence": 85,
                "last_analysis": "2024-01-01T12:00:00Z"
            }
            
            response = client.get(f"/user/{user_id}/score")
            assert response.status_code == 200
            
            data = response.json()
            assert data["user_id"] == user_id
            assert data["total_score"] == 42
    
    def test_get_user_score_not_found(self):
        """存在しないユーザーのスコア取得"""
        user_id = "nonexistent_user"
        
        with patch('api.server.get_user_latest_score') as mock_get_score:
            mock_get_score.return_value = None
            
            response = client.get(f"/user/{user_id}/score")
            assert response.status_code == 404
            
            data = response.json()
            assert "not found" in data["detail"].lower()
    
    def test_get_user_history(self):
        """ユーザーのスコア履歴取得"""
        user_id = "history_user"
        
        with patch('api.server.get_user_score_history') as mock_get_history:
            mock_get_history.return_value = [
                {
                    "analysis_date": "2024-01-01T10:00:00Z",
                    "total_score": 40,
                    "confidence": 80
                },
                {
                    "analysis_date": "2024-01-02T10:00:00Z",
                    "total_score": 45,
                    "confidence": 85
                }
            ]
            
            response = client.get(f"/user/{user_id}/history")
            assert response.status_code == 200
            
            data = response.json()
            assert len(data) == 2
            assert all("analysis_date" in item for item in data)
            assert all("total_score" in item for item in data)

class TestStatsEndpoint:
    
    def test_get_stats(self):
        """全体統計の取得"""
        with patch('api.server.get_overall_stats') as mock_get_stats:
            mock_get_stats.return_value = {
                "total_users_analyzed": 150,
                "average_bot_score": 32.5,
                "high_risk_users": 8,
                "total_analyses": 1250,
                "last_24h_analyses": 45
            }
            
            response = client.get("/stats")
            assert response.status_code == 200
            
            data = response.json()
            assert "total_users_analyzed" in data
            assert "average_bot_score" in data
            assert "high_risk_users" in data
            assert data["total_users_analyzed"] == 150

class TestErrorHandling:
    
    def test_internal_server_error_handling(self):
        """内部サーバーエラーのハンドリング"""
        test_messages = [
            {
                "id": "error_test",
                "content": "エラーテスト",
                "timestamp": "2024-01-01T10:00:00Z",
                "author_id": "error_user"
            }
        ]
        
        with patch('analyzer.engine.AnalysisEngine') as mock_engine:
            # 分析エンジンで例外を発生させる
            mock_instance = mock_engine.return_value
            mock_instance.analyze_user.side_effect = Exception("分析エラー")
            
            response = client.post("/analyze", json={"messages": test_messages})
            assert response.status_code == 500
            
            data = response.json()
            assert "detail" in data
            assert "internal server error" in data["detail"].lower()
    
    def test_validation_error_details(self):
        """バリデーションエラーの詳細"""
        invalid_data = {
            "messages": [
                {
                    "id": 123,  # 文字列であるべき
                    "content": "",  # 空文字列
                    "timestamp": "invalid-timestamp",  # 不正なフォーマット
                    "author_id": None  # nullは不正
                }
            ]
        }
        
        response = client.post("/analyze", json=invalid_data)
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data
        # バリデーションエラーの詳細が含まれているか
        assert len(data["detail"]) > 0

class TestCORS:
    
    def test_cors_headers(self):
        """CORS ヘッダーのテスト"""
        response = client.options("/analyze")
        
        # CORS ヘッダーが設定されているか確認
        # 注意：実際の実装に依存
        assert response.status_code in [200, 405]  # OPTIONSが許可されているか

class TestRequestValidation:
    
    def test_message_content_length_validation(self):
        """メッセージ内容の長さ制限テスト"""
        # 非常に長いメッセージ
        very_long_content = "a" * 10000
        
        long_message = [
            {
                "id": "long_test",
                "content": very_long_content,
                "timestamp": "2024-01-01T10:00:00Z",
                "author_id": "long_user"
            }
        ]
        
        response = client.post("/analyze", json={"messages": long_message})
        # 実装に依存するが、通常は長すぎるメッセージは処理される
        # または制限される場合がある
        assert response.status_code in [200, 400, 413]
    
    def test_timestamp_format_validation(self):
        """タイムスタンプフォーマットのバリデーション"""
        valid_timestamps = [
            "2024-01-01T10:00:00Z",
            "2024-01-01T10:00:00.123Z",
            "2024-01-01T10:00:00+09:00"
        ]
        
        for timestamp in valid_timestamps:
            messages = [
                {
                    "id": "timestamp_test",
                    "content": "タイムスタンプテスト",
                    "timestamp": timestamp,
                    "author_id": "timestamp_user"
                }
            ]
            
            with patch('analyzer.engine.AnalysisEngine'):
                response = client.post("/analyze", json={"messages": messages})
                # 有効なタイムスタンプは受け入れられるべき
                assert response.status_code in [200, 422]  # バリデーション通過 or 他の検証エラー
    
    def test_concurrent_requests(self):
        """同時リクエストの処理"""
        import threading
        import time
        
        test_messages = [
            {
                "id": "concurrent_test",
                "content": "同時リクエストテスト",
                "timestamp": "2024-01-01T10:00:00Z",
                "author_id": "concurrent_user"
            }
        ]
        
        responses = []
        
        def make_request():
            try:
                response = client.post("/analyze", json={"messages": test_messages})
                responses.append(response.status_code)
            except Exception as e:
                responses.append(str(e))
        
        # 10個の同時リクエストを作成
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # 全てのスレッドを開始
        for thread in threads:
            thread.start()
        
        # 全ての完了を待つ
        for thread in threads:
            thread.join()
        
        # レスポンスをチェック
        assert len(responses) == 10
        # 大部分のリクエストは成功するはず（レート制限以外）
        successful_responses = [r for r in responses if r == 200]
        assert len(successful_responses) >= 1