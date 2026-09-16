<script setup lang="ts">
import { computed, ref } from 'vue'
import { Delete, PictureFilled, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles, UploadUserFile } from 'element-plus'

const props = defineProps<{
  previewUrl: string
  uploading: boolean
}>()

const emit = defineEmits<{
  selected: [file: File]
  cleared: []
}>()

const fileList = ref<UploadUserFile[]>([])
const hasImage = computed(() => Boolean(props.previewUrl))

function handleChange(file: UploadFile, _files: UploadFiles): void {
  if (!file.raw) return
  const accepted = ['image/png', 'image/jpeg'].includes(file.raw.type)
  if (!accepted) {
    fileList.value = []
    return
  }
  fileList.value = [file]
  emit('selected', file.raw)
}

function clear(): void {
  fileList.value = []
  emit('cleared')
}
</script>

<template>
  <div class="upload-shell" :class="{ 'has-image': hasImage }">
    <div v-if="hasImage" class="upload-preview">
      <img :src="previewUrl" alt="待转换原图预览" />
      <div class="upload-preview-actions">
        <span><el-icon><PictureFilled /></el-icon> 图片已就绪</span>
        <el-button :icon="Delete" text type="danger" :disabled="uploading" @click="clear">
          移除
        </el-button>
      </div>
    </div>
    <el-upload
      v-else
      v-model:file-list="fileList"
      class="upload-control"
      drag
      accept="image/png,image/jpeg"
      :auto-upload="false"
      :limit="1"
      :show-file-list="false"
      :on-change="handleChange"
      :disabled="uploading"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="upload-title">拖入 PNG 或 JPG 图片</div>
      <div class="upload-hint">或点击选择文件，最大 20 MB</div>
    </el-upload>
  </div>
</template>
