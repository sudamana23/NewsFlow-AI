"""
LM Studio Integration with Auto-Detection
Automatically detects and uses whatever model is currently running in LM Studio
"""

import httpx
import asyncio
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

class LMStudioManager:
    """Manages LM Studio connection and auto-detects current model"""
    
    def __init__(self):
        self.base_url = settings.lm_studio_url
        self.client = httpx.AsyncClient(timeout=10.0)
        self._current_model = None
        self._last_check = 0
        self._check_interval = 300  # Check every 5 minutes
    
    async def get_current_model(self) -> str:
        """Get the currently active model in LM Studio"""
        import time
        
        # Use cached model if recent
        if (self._current_model and 
            time.time() - self._last_check < self._check_interval):
            return self._current_model
        
        try:
            # Try to detect current model
            detected_model = await self._detect_active_model()
            
            if detected_model:
                self._current_model = detected_model
                self._last_check = time.time()
                logger.info(f"🤖 Detected LM Studio model: {detected_model}")
                return detected_model
            else:
                logger.warning("⚠️ Could not detect LM Studio model, using fallback")
                return settings.lm_studio_fallback_model
                
        except Exception as e:
            logger.error(f"❌ Error detecting LM Studio model: {e}")
            return settings.lm_studio_fallback_model
    
    async def _detect_active_model(self) -> Optional[str]:
        """Detect which model is currently active in LM Studio"""
        try:
            # Method 1: Try to get available models
            models = await self._get_available_models()
            
            if models:
                # Usually LM Studio has one active model
                if len(models) == 1:
                    return models[0]["id"]
                
                # If multiple models, try to find the active one
                for model in models:
                    # Some LM Studio versions mark active models
                    if model.get("active", False):
                        return model["id"]
                
                # Fallback: use first model
                return models[0]["id"]
            
            # Method 2: Try to make a test completion to see what model responds
            test_model = await self._test_model_response()
            if test_model:
                return test_model
                
            return None
            
        except Exception as e:
            logger.error(f"Error in model detection: {e}")
            return None
    
    async def _get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from LM Studio"""
        try:
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            result = response.json()
            
            if "data" in result:
                models = result["data"]
                logger.info(f"📋 Found {len(models)} available models in LM Studio")
                return models
            
            return []
            
        except Exception as e:
            logger.debug(f"Could not get models list: {e}")
            return []
    
    async def _test_model_response(self) -> Optional[str]:
        """Test model response to detect active model"""
        try:
            # Try with generic model name that LM Studio often accepts
            test_models = ["local-model", "gpt-3.5-turbo", "model"]
            
            for test_model in test_models:
                try:
                    response = await self.client.post(
                        f"{self.base_url}/chat/completions",
                        json={
                            "model": test_model,
                            "messages": [{"role": "user", "content": "Hi"}],
                            "max_tokens": 1,
                            "temperature": 0
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Check if response contains model info
                        if "model" in result:
                            return result["model"]
                        else:
                            return test_model  # Model worked, use the test name
                            
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Model test failed: {e}")
            return None
    
    async def is_available(self) -> bool:
        """Check if LM Studio is available and responsive"""
        try:
            response = await self.client.get(f"{self.base_url}/models", timeout=5.0)
            return response.status_code == 200
        except:
            return False
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        try:
            model_name = await self.get_current_model()
            is_available = await self.is_available()
            
            return {
                "model_name": model_name,
                "is_available": is_available,
                "base_url": self.base_url,
                "auto_detected": model_name != settings.lm_studio_fallback_model
            }
            
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return {
                "model_name": settings.lm_studio_fallback_model,
                "is_available": False,
                "base_url": self.base_url,
                "auto_detected": False,
                "error": str(e)
            }
    
    def force_refresh(self):
        """Force refresh of model detection on next call"""
        self._current_model = None
        self._last_check = 0
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global instance
lm_studio_manager = LMStudioManager()
