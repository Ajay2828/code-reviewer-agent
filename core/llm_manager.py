import time
import asyncio
import boto3
import json
from typing import Optional, Dict, Any, AsyncGenerator
from openai import AzureOpenAI
import tiktoken
import structlog

from config.settings import get_settings, COST_PER_1K_TOKENS

logger = structlog.get_logger()
settings = get_settings()


class LLMManager:
    """
    Manages LLM interactions with Bedrock (Claude) and Azure OpenAI (GPT-4o)
    """
    
    def __init__(self):
        self.bedrock_client = self._init_bedrock()
        self.azure_client = self._init_azure()
        self.total_cost = 0.0
        self.request_count = 0
        
    def _init_bedrock(self):
        """Initialize AWS Bedrock client for Claude"""
        try:
            session = boto3.session.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            bedrock_runtime = session.client(
                service_name='bedrock-runtime',
                region_name=settings.AWS_REGION
            )
            
            logger.info("bedrock_client_initialized", region=settings.AWS_REGION)
            return bedrock_runtime
            
        except Exception as e:
            logger.error(f"bedrock_init_failed: {e}")
            return None
    
    def _init_azure(self):
        """Initialize Azure OpenAI client"""
        try:
            client = AzureOpenAI(
                api_version=settings.AZURE_API_VERSION,
                azure_endpoint=settings.AZURE_ENDPOINT,
                api_key=settings.AZURE_API_KEY,
            )
            
            logger.info("azure_client_initialized", endpoint=settings.AZURE_ENDPOINT)
            return client
            
        except Exception as e:
            logger.error(f"azure_init_failed: {e}")
            return None
    
    def _count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text for cost estimation"""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}, using estimate")
            return len(text) // 4  # Rough estimate
    
    def _calculate_cost(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> float:
        """Calculate cost for API call"""
        if model not in COST_PER_1K_TOKENS:
            logger.warning(f"Unknown model for cost calculation: {model}")
            return 0.0
        
        costs = COST_PER_1K_TOKENS[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return input_cost + output_cost
    
    async def _generate_with_bedrock(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response using AWS Bedrock (Claude Haiku)
        """
        if not self.bedrock_client:
            raise Exception("Bedrock client not initialized")
        
        model_id = settings.BEDROCK_MODEL_ID
        
        # Count input tokens
        input_text = system_prompt + user_prompt
        input_tokens = self._count_tokens(input_text, "claude-haiku-4-5")
        
        # Prepare request body for Claude via Bedrock
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": settings.MAX_TOKENS,
            "temperature": settings.TEMPERATURE,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        start_time = time.time()
        
        try:
            # Invoke Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            # Extract token usage
            usage = response_body.get('usage', {})
            output_tokens = usage.get('output_tokens', self._count_tokens(content, "claude-haiku-4-5"))
            actual_input_tokens = usage.get('input_tokens', input_tokens)
            
            # Calculate cost (Claude Haiku pricing)
            cost = self._calculate_cost("claude-haiku-4-5", actual_input_tokens, output_tokens)
            self.total_cost += cost
            self.request_count += 1
            
            elapsed = time.time() - start_time
            
            logger.info(
                "bedrock_generation_complete",
                model="claude-haiku-4-5",
                input_tokens=actual_input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                elapsed=elapsed
            )
            
            return {
                "content": content,
                "model": "claude-haiku-4-5-bedrock",
                "cost": cost,
                "tokens": {
                    "input": actual_input_tokens,
                    "output": output_tokens
                },
                "elapsed": elapsed
            }
            
        except Exception as e:
            logger.error(f"Bedrock generation failed: {e}")
            raise
    
    async def _generate_with_azure(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response using Azure OpenAI (GPT-4o)
        """
        if not self.azure_client:
            raise Exception("Azure client not initialized")
        
        # Count input tokens
        input_text = system_prompt + user_prompt
        input_tokens = self._count_tokens(input_text, "gpt-4o")
        
        start_time = time.time()
        
        try:
            # Call Azure OpenAI
            response = self.azure_client.chat.completions.create(
                model=settings.AZURE_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
            )
            
            content = response.choices[0].message.content
            
            # Extract token usage
            usage = response.usage
            actual_input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            
            # Calculate cost (GPT-4o pricing)
            cost = self._calculate_cost("gpt-4o", actual_input_tokens, output_tokens)
            self.total_cost += cost
            self.request_count += 1
            
            elapsed = time.time() - start_time
            
            logger.info(
                "azure_generation_complete",
                model="gpt-4o",
                input_tokens=actual_input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                elapsed=elapsed
            )
            
            return {
                "content": content,
                "model": "gpt-4o-azure",
                "cost": cost,
                "tokens": {
                    "input": actual_input_tokens,
                    "output": output_tokens
                },
                "elapsed": elapsed
            }
            
        except Exception as e:
            logger.error(f"Azure generation failed: {e}")
            raise
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        use_fallback: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response with automatic fallback
        
        Primary: AWS Bedrock (Claude Haiku) - cheaper, good quality
        Fallback: Azure OpenAI (GPT-4o) - more expensive, very reliable
        
        Returns:
            {
                "content": str,
                "model": str,
                "cost": float,
                "tokens": {"input": int, "output": int}
            }
        """
        try:
            if not use_fallback:
                # Try Bedrock first (Claude Haiku - cheaper!)
                return await self._generate_with_bedrock(system_prompt, user_prompt, **kwargs)
            else:
                # Use Azure as fallback
                return await self._generate_with_azure(system_prompt, user_prompt, **kwargs)
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            
            # If primary fails and we haven't tried fallback, try it
            if not use_fallback:
                logger.info("Attempting fallback to Azure OpenAI")
                return await self.generate(
                    system_prompt, 
                    user_prompt, 
                    use_fallback=True, 
                    **kwargs
                )
            else:
                raise Exception(f"Both primary and fallback LLMs failed: {e}")
    
    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        use_fallback: bool = False,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response
        
        Note: Bedrock streaming is more complex, so this uses Azure for streaming
        """
        if not self.azure_client:
            raise Exception("Azure client not initialized")
        
        try:
            response = self.azure_client.chat.completions.create(
                model=settings.AZURE_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_requests": self.request_count,
            "total_cost": round(self.total_cost, 4),
            "avg_cost_per_request": round(
                self.total_cost / max(self.request_count, 1), 4
            )
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.total_cost = 0.0
        self.request_count = 0


# Singleton instance
_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get or create LLM manager instance"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager