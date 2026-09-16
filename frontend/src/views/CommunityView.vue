<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ChatDotRound, Download, FullScreen, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { assetUrl, fetchCommunityArtworks } from '../api'
import { useAuthStore } from '../stores/auth'
import type { Artwork } from '../types'

const artworks = ref<Artwork[]>([])
const loading = ref(false)
const previewVisible = ref(false)
const previewArtwork = ref<Artwork | null>(null)
const previewType = ref<'number' | 'color'>('number')
const auth = useAuthStore()

onMounted(() => void load())

async function load(): Promise<void> {
  loading.value = true
  try {
    artworks.value = await fetchCommunityArtworks(60)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '社区作品加载失败')
  } finally {
    loading.value = false
  }
}

function download(path: string): void {
  window.open(assetUrl(path), '_blank', 'noopener,noreferrer')
}

function openPreview(item: Artwork): void {
  previewArtwork.value = item
  previewType.value = 'number'
  previewVisible.value = true
}

function formatDate(value: string | null): string {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
}
</script>

<template>
  <main class="catalog-page">
    <section class="community-hero">
      <div>
        <p class="eyebrow">COMMUNITY</p>
        <h1>拼豆灵感社区</h1>
        <p>发现其他创作者公开分享的 MARD 拼豆图纸，预览作品并免费下载制作文件。</p>
      </div>
      <el-button :icon="RefreshRight" :loading="loading" @click="load">刷新作品</el-button>
    </section>

    <section v-loading="loading" class="artwork-grid" aria-live="polite">
      <article v-for="item in artworks" :key="item.job_id" class="artwork-card">
        <div class="artwork-cover">
          <img :src="assetUrl(item.number_preview_url)" :alt="item.title" loading="lazy" />
          <span class="public-pill">公开作品</span>
        </div>
        <div class="artwork-body">
          <div class="artwork-owner">
            <span class="avatar">{{ item.username.slice(0, 1).toUpperCase() }}</span>
            <div><strong>{{ item.username }}</strong><small>{{ formatDate(item.published_at) }}</small></div>
          </div>
          <h2>{{ item.title }}</h2>
          <p v-if="item.description" class="artwork-description">{{ item.description }}</p>
          <div class="artwork-meta">
            <span>{{ item.size }}</span><span>{{ item.palette === 'mard_291' ? 'MARD 291' : 'MARD 221' }}</span><span>{{ item.active_bead_count.toLocaleString() }} 颗</span>
          </div>
          <div class="artwork-actions">
            <el-button :icon="FullScreen" @click="openPreview(item)">在线预览</el-button>
            <el-button type="primary" :icon="Download" @click="download(item.pdf_url)">下载 PDF</el-button>
            <el-dropdown trigger="click" @command="(path: string) => download(path)">
              <el-button>更多下载</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :command="item.png_url">PNG 图纸</el-dropdown-item>
                  <el-dropdown-item :command="item.csv_url">材料 CSV</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <RouterLink
              v-if="auth.user.value && auth.user.value.id !== item.user_id"
              :to="{ path: '/chat', query: { user: item.user_id, name: item.username } }"
              class="contact-author"
            ><el-button text :icon="ChatDotRound">联系作者</el-button></RouterLink>
            <span class="download-count">{{ item.download_count }} 次下载</span>
          </div>
        </div>
      </article>
    </section>

    <el-empty v-if="!loading && artworks.length === 0" description="社区还没有公开作品，登录后发布第一张吧">
      <RouterLink to="/register"><el-button type="primary">加入社区</el-button></RouterLink>
    </el-empty>

    <el-dialog v-model="previewVisible" width="min(1100px, 94vw)" class="community-preview-dialog" destroy-on-close>
      <template #header>
        <div v-if="previewArtwork" class="preview-dialog-title">
          <div><p class="eyebrow">在线预览</p><h2>{{ previewArtwork.title }}</h2></div>
          <span>作者：{{ previewArtwork.username }}</span>
        </div>
      </template>
      <template v-if="previewArtwork">
        <div class="community-preview-controls">
          <el-radio-group v-model="previewType">
            <el-radio-button value="number">MARD 色号图</el-radio-button>
            <el-radio-button value="color">纯色块图</el-radio-button>
          </el-radio-group>
          <span>{{ previewArtwork.size }} · {{ previewArtwork.active_bead_count.toLocaleString() }} 颗拼豆</span>
        </div>
        <div class="community-preview-canvas">
          <img
            :src="assetUrl(previewType === 'number' ? previewArtwork.number_preview_url : previewArtwork.color_preview_url)"
            :alt="`${previewArtwork.title}在线预览`"
          />
        </div>
        <p v-if="previewArtwork.description" class="preview-dialog-description">{{ previewArtwork.description }}</p>
      </template>
    </el-dialog>
  </main>
</template>
