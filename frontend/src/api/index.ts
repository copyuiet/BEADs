import type {
  Artwork,
  AuthResult,
  ChatMessage,
  ChatUser,
  Credentials,
  GeneratePayload,
  GenerateResult,
  PaletteOption,
  Specification,
  UploadResult,
  User,
  PublishArtworkPayload,
} from '../types'

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function endpoint(path: string): string {
  return `${apiBase}${path}`
}

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers)
  const token = localStorage.getItem('bead_access_token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(endpoint(path), { ...options, headers })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // 保留通用错误信息
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  const token = localStorage.getItem('bead_access_token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(endpoint(path), { headers })
  if (!response.ok) throw new Error(`下载失败（${response.status}）`)
  return response.blob()
}

export async function uploadImage(file: File): Promise<UploadResult> {
  const body = new FormData()
  body.append('file', file)
  return requestJson<UploadResult>('/api/upload', { method: 'POST', body })
}

export async function generatePattern(payload: GeneratePayload): Promise<GenerateResult> {
  return requestJson<GenerateResult>('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function fetchPalettes(): Promise<PaletteOption[]> {
  return requestJson<PaletteOption[]>('/api/palettes')
}

export function fetchSpecifications(): Promise<Specification[]> {
  return requestJson<Specification[]>('/api/specifications')
}

export function registerAccount(payload: Credentials): Promise<AuthResult> {
  return requestJson<AuthResult>('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function loginAccount(payload: Credentials): Promise<AuthResult> {
  return requestJson<AuthResult>('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function fetchCurrentUser(): Promise<User> {
  return requestJson<User>('/api/auth/me')
}

export function fetchMyArtworks(): Promise<Artwork[]> {
  return requestJson<Artwork[]>('/api/me/artworks')
}

export function fetchCommunityArtworks(limit = 24, offset = 0): Promise<Artwork[]> {
  return requestJson<Artwork[]>(`/api/community?limit=${limit}&offset=${offset}`)
}

export function publishArtwork(jobId: string, payload: PublishArtworkPayload): Promise<Artwork> {
  return requestJson<Artwork>(`/api/artworks/${jobId}/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function saveArtwork(jobId: string): Promise<Artwork> {
  return requestJson<Artwork>(`/api/artworks/${jobId}/save`, { method: 'POST' })
}

export async function deleteArtwork(jobId: string): Promise<void> {
  const headers = new Headers()
  const token = localStorage.getItem('bead_access_token')
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(endpoint(`/api/artworks/${jobId}`), { method: 'DELETE', headers })
  if (!response.ok) throw new Error(`删除失败（${response.status}）`)
}

export function unpublishArtwork(jobId: string): Promise<Artwork> {
  return requestJson<Artwork>(`/api/artworks/${jobId}/unpublish`, { method: 'POST' })
}

export function searchChatUsers(query = ''): Promise<ChatUser[]> {
  return requestJson<ChatUser[]>(`/api/chat/users?query=${encodeURIComponent(query)}`)
}

export function fetchConversations(): Promise<ChatUser[]> {
  return requestJson<ChatUser[]>('/api/chat/conversations')
}

export function fetchMessages(userId: string, afterId = 0): Promise<ChatMessage[]> {
  return requestJson<ChatMessage[]>(`/api/chat/${userId}/messages?after_id=${afterId}`)
}

export function sendChatMessage(userId: string, body: string): Promise<ChatMessage> {
  return requestJson<ChatMessage>(`/api/chat/${userId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body }),
  })
}

export async function downloadPrivateAsset(path: string, filename: string): Promise<void> {
  const blob = await requestBlob(path)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function hasStoredToken(): boolean {
  return Boolean(localStorage.getItem('bead_access_token'))
}

export function assetUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return endpoint(path)
}
