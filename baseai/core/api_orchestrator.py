"""Module for orchestrating asynchronous API calls to external services."""

import logging
import os
from typing import Any, Dict
import httpx
from unittest.mock import AsyncMock, patch
import pytest

# Configure logging with a more informative format
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_api_key(env_var: str = "GEMINI_API_KEY") -> str:
    """Retrieves an API key from an environment variable.

    Args:
        env_var: The name of the environment variable to retrieve.

    Returns:
        The API key.

    Raises:
        ValueError: If the environment variable is not set.
    """
    api_key = os.getenv(env_var)
    if not api_key:
        error_msg = f"'{env_var}' environment variable not set."
        logger.error(error_msg)
        raise ValueError(error_msg)
    return api_key


async def make_api_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: Dict[str, str] | None = None,
    json_data: Dict[str, Any] | None = None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Makes an asynchronous API request.

    This function uses an httpx.AsyncClient for connection pooling and performance.
    It automatically raises an exception for HTTP 4xx or 5xx responses.

    Args:
        client: An initialized httpx.AsyncClient instance.
        method: The HTTP method (e.g., "GET", "POST").
        url: The full URL for the API endpoint.
        headers: An optional dictionary of request headers.
        json_data: An optional dictionary to be sent as the JSON request body.
        params: An optional dictionary of URL query parameters.

    Returns:
        The JSON response from the API as a dictionary.

    Raises:
        httpx.HTTPStatusError: If the API returns a 4xx or 5xx status code.
        httpx.RequestError: For network-related errors like timeouts or connection
            failures.
    """
    logger.info("Making %s request to %s", method, url)
    try:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json_data,
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP error %s for %s %s: %s",
            exc.response.status_code,
            exc.request.method,
            exc.request.url,
            exc.response.text,
        )
        raise
    except httpx.RequestError as exc:
        logger.error("Request error for %s %s: %s", exc.request.method, exc.request.url, exc)
        raise

@pytest.mark.asyncio
async def test_get_api_key():
    with patch('os.getenv', return_value='test_key'):
        assert get_api_key() == 'test_key'
    with patch('os.getenv', return_value=None):
        with pytest.raises(ValueError):
            get_api_key()

@pytest.mark.asyncio
async def test_make_api_request():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: {'result': 'success'}, raise_for_status=AsyncMock()))
    response = await make_api_request(client, 'GET', 'https://api.example.com', {'Authorization': 'Bearer test'}, {'data': 'value'}, {'param': 'value'})
    assert response == {'result': 'success'}
    client.request.assert_called_once_with(
        method='GET',
        url='https://api.example.com',
        headers={'Authorization': 'Bearer test'},
        json={'data': 'value'},
        params={'param': 'value'},
        timeout=30.0
    )
    client.request = AsyncMock(side_effect=httpx.HTTPStatusError(message='Error', request=AsyncMock(), response=AsyncMock(status_code=404)))
    with pytest.raises(httpx.HTTPStatusError):
        await make_api_request(client, 'GET', 'https://api.failure.com')
    client.request = AsyncMock(side_effect=httpx.RequestError(message='Connection error', request=AsyncMock()))
    with pytest.raises(httpx.RequestError):
        await make_api_request(client, 'GET', 'https://api.failure.com')