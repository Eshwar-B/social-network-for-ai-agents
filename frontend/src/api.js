const API_BASE = '/api/v1';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function fetchAgents(limit = 100) {
  const res = await fetch(`${API_BASE}/agents?limit=${limit}`);
  return res.json();
}

export async function registerAgent(payload) {
  const res = await fetch(`${API_BASE}/agents/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Registration failed');
  }
  return res.json();
}

export async function toggleAgentActive(agentId, activate, apiKey) {
  const endpoint = activate ? 'activate' : 'deactivate';
  const res = await fetch(`${API_BASE}/agents/${agentId}/${endpoint}`, {
    method: 'POST',
    headers: { 'X-Agent-API-Key': apiKey },
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Activation toggle failed');
  }
  return res.json();
}

export async function fetchPosts(limit = 100) {
  const res = await fetch(`${API_BASE}/posts?limit=${limit}`);
  return res.json();
}

export async function createPost(payload, apiKey) {
  const res = await fetch(`${API_BASE}/posts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Agent-API-Key': apiKey,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to publish post');
  }
  return res.json();
}

export async function fetchPostComments(postId) {
  const res = await fetch(`${API_BASE}/posts/${postId}/comments`);
  return res.json();
}

export async function fetchRoutingLogs(postId) {
  const res = await fetch(`${API_BASE}/posts/${postId}/routing-logs`);
  return res.json();
}
