export type GridSize = '52x52' | '80x80' | '104x104'
export type PaletteKey = 'mard_221' | 'mard_291'
export type ColorMode = 'lab' | 'rgb'
export type ResizeMode = 'fit_pad' | 'crop_fill'
export type PatternType = 'color' | 'number'

export interface UploadResult {
  image_id: string
  original_url: string
  width: number
  height: number
}

export interface PaletteOption {
  key: PaletteKey
  label: string
  color_count: number
}

export interface Specification {
  key: GridSize
  columns: number
  rows: number
  bead_count: number
  width_mm: number
  height_mm: number
}

export interface ColorStatistic {
  code: string
  name: string | null
  hex: string
  rgb: [number, number, number]
  count: number
  percentage: number
}

export interface GeneratePayload {
  image_id: string
  size: GridSize
  palette: PaletteKey
  color_mode: ColorMode
  dithering: boolean
  pattern_type: PatternType
  resize_mode: ResizeMode
  content_scale: number
}

export interface GenerateResult {
  job_id: string
  preview_url: string
  color_preview_url: string
  number_preview_url: string
  png_url: string
  pdf_url: string
  csv_url: string
  specification: Specification
  palette: PaletteKey
  color_mode: ColorMode
  dithering: boolean
  active_bead_count: number
  statistics: ColorStatistic[]
}

export interface User {
  id: string
  username: string
  created_at: string
}

export interface AuthResult {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export interface Credentials {
  username: string
  password: string
}

export interface Artwork {
  job_id: string
  user_id: string
  username: string
  title: string
  description: string
  size: GridSize
  palette: PaletteKey
  color_mode: ColorMode
  dithering: boolean
  pattern_type: PatternType
  active_bead_count: number
  is_saved: boolean
  is_public: boolean
  created_at: string
  published_at: string | null
  download_count: number
  color_preview_url: string
  number_preview_url: string
  png_url: string
  pdf_url: string
  csv_url: string
}

export interface PublishArtworkPayload {
  title: string
  description: string
}

export interface ChatUser {
  id: string
  username: string
  last_message: string | null
  last_message_at: string | null
  unread_count: number
}

export interface ChatMessage {
  id: number
  sender_id: string
  recipient_id: string
  body: string
  created_at: string
  read_at: string | null
}
