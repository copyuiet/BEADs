<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Delete, Download, Promotion, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { assetUrl, deleteArtwork, downloadPrivateAsset, fetchMyArtworks, publishArtwork, unpublishArtwork } from '../api'
import type { Artwork } from '../types'

const artworks = ref<Artwork[]>([])
const loading = ref(false)
const publishing = ref(false)
const dialogVisible = ref(false)
const selected = ref<Artwork | null>(null)
const publishForm = reactive({ title: '', description: '' })

onMounted(() => void load())

async function load(): Promise<void> {
  loading.value = true
  try {
    artworks.value = await fetchMyArtworks()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '个人作品加载失败')
  } finally {
    loading.value = false
  }
}

function openPublish(item: Artwork): void {
  selected.value = item
  publishForm.title = item.title
  publishForm.description = item.description
  dialogVisible.value = true
}

async function confirmPublish(): Promise<void> {
  if (!selected.value || !publishForm.title.trim()) {
    ElMessage.warning('请填写作品标题')
    return
  }
  publishing.value = true
  try {
    const updated = await publishArtwork(selected.value.job_id, publishForm)
    replaceArtwork(updated)
    dialogVisible.value = false
    ElMessage.success('作品已发布到社区')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '发布失败')
  } finally {
    publishing.value = false
  }
}

async function unpublish(item: Artwork): Promise<void> {
  try {
    await ElMessageBox.confirm('取消公开后，社区中的其他用户将无法继续查看和下载。', '取消发布', { type: 'warning' })
    replaceArtwork(await unpublishArtwork(item.job_id))
    ElMessage.success('作品已转为私有')
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message)
  }
}

async function remove(item: Artwork): Promise<void> {
  try {
    await ElMessageBox.confirm(
      item.is_public ? '该作品已发布到社区，删除后社区内容和所有生成文件都会永久移除。' : '删除后该作品及生成文件将永久移除。',
      '删除作品',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    await deleteArtwork(item.job_id)
    artworks.value = artworks.value.filter((artwork) => artwork.job_id !== item.job_id)
    ElMessage.success('作品已删除')
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message)
  }
}

async function download(path: string, filename: string): Promise<void> {
  try {
    await downloadPrivateAsset(path, filename)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '下载失败')
  }
}

function replaceArtwork(updated: Artwork): void {
  const index = artworks.value.findIndex((item) => item.job_id === updated.job_id)
  if (index >= 0) artworks.value[index] = updated
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
</script>

<template>
  <main class="catalog-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">MY COLLECTION</p>
        <h1>我的作品</h1>
        <p>只有在创作区点击“保存到我的作品”的图纸才会出现在这里，满意后还可以发布到社区。</p>
      </div>
      <div class="heading-actions">
        <RouterLink to="/"><el-button type="primary">创建新图纸</el-button></RouterLink>
        <el-button :icon="RefreshRight" :loading="loading" @click="load">刷新</el-button>
      </div>
    </section>

    <section v-loading="loading" class="artwork-grid">
      <article v-for="item in artworks" :key="item.job_id" class="artwork-card">
        <div class="artwork-cover">
          <img :src="assetUrl(item.number_preview_url)" :alt="item.title" loading="lazy" />
          <span :class="['visibility-pill', { public: item.is_public }]">{{ item.is_public ? '已公开' : '仅自己可见' }}</span>
        </div>
        <div class="artwork-body">
          <h2>{{ item.title }}</h2>
          <p class="created-time">{{ formatDate(item.created_at) }}</p>
          <div class="artwork-meta">
            <span>{{ item.size }}</span><span>{{ item.palette === 'mard_291' ? 'MARD 291' : 'MARD 221' }}</span><span>{{ item.active_bead_count.toLocaleString() }} 颗</span>
          </div>
          <div class="artwork-actions own-actions">
            <el-button :icon="Download" @click="download(item.pdf_url, `${item.title}.pdf`)">PDF</el-button>
            <el-button @click="download(item.png_url, `${item.title}.png`)">PNG</el-button>
            <el-button v-if="!item.is_public" type="primary" :icon="Promotion" @click="openPublish(item)">发布</el-button>
            <el-button v-else type="danger" plain @click="unpublish(item)">取消公开</el-button>
            <el-button type="danger" plain :icon="Delete" @click="remove(item)">删除</el-button>
          </div>
        </div>
      </article>
    </section>

    <el-empty v-if="!loading && artworks.length === 0" description="还没有作品，先生成第一张拼豆图纸吧">
      <RouterLink to="/"><el-button type="primary">开始创作</el-button></RouterLink>
    </el-empty>

    <el-dialog v-model="dialogVisible" title="发布到拼豆社区" width="min(520px, 92vw)">
      <el-form label-position="top">
        <el-form-item label="作品标题">
          <input v-model="publishForm.title" class="form-control" maxlength="80" />
        </el-form-item>
        <el-form-item label="作品介绍">
          <textarea v-model="publishForm.description" class="form-control form-textarea" rows="4" maxlength="500" placeholder="介绍灵感、用途或制作心得（选填）"></textarea>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="confirmPublish">确认公开发布</el-button>
      </template>
    </el-dialog>
  </main>
</template>
