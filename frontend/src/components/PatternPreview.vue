<script setup lang="ts">
import { computed } from 'vue'
import { Check, Download, Document, Grid, ZoomIn, ZoomOut } from '@element-plus/icons-vue'

import { assetUrl } from '../api'
import type { GenerateResult, PatternType } from '../types'

const props = defineProps<{
  result: GenerateResult
  originalUrl: string
  patternType: PatternType
  zoom: number
  saved: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  'update:patternType': [value: PatternType]
  'update:zoom': [value: number]
  download: [kind: 'png' | 'pdf' | 'csv']
  save: []
}>()

const activePreview = computed(() =>
  assetUrl(props.patternType === 'number' ? props.result.number_preview_url : props.result.color_preview_url),
)

function setZoom(value: number): void {
  emit('update:zoom', Math.max(25, Math.min(300, value)))
}
</script>

<template>
  <section class="result-card" aria-labelledby="preview-title">
    <header class="result-toolbar">
      <div>
        <p class="eyebrow">生成结果</p>
        <h2 id="preview-title">可制作拼豆图纸</h2>
      </div>
      <div class="download-actions">
        <el-button
          :type="saved ? 'success' : 'primary'"
          :icon="Check"
          :loading="saving"
          :disabled="saved"
          @click="emit('save')"
        >{{ saved ? '已保存到我的作品' : '保存到我的作品' }}</el-button>
        <el-button :icon="Download" @click="emit('download', 'png')">PNG</el-button>
        <el-button :icon="Document" @click="emit('download', 'pdf')">PDF</el-button>
        <el-button :icon="Grid" @click="emit('download', 'csv')">材料 CSV</el-button>
      </div>
    </header>

    <div class="comparison-strip">
      <div class="original-tile">
        <span>原图</span>
        <img :src="originalUrl" alt="上传的原始图片" />
      </div>
      <div class="result-summary">
        <strong>{{ result.specification.key }}</strong>
        <span>实际 {{ result.active_bead_count.toLocaleString() }} 颗</span>
        <span>板容量 {{ result.specification.bead_count.toLocaleString() }} 颗</span>
        <span>{{ result.specification.width_mm }} × {{ result.specification.height_mm }} mm</span>
      </div>
    </div>

    <div class="preview-controls">
      <el-radio-group
        :model-value="patternType"
        @update:model-value="emit('update:patternType', $event as PatternType)"
      >
        <el-radio-button value="color">纯色块</el-radio-button>
        <el-radio-button value="number">MARD 色号</el-radio-button>
      </el-radio-group>
      <div class="zoom-control" aria-label="图纸缩放">
        <el-button circle :icon="ZoomOut" aria-label="缩小" @click="setZoom(zoom - 25)" />
        <el-slider
          :model-value="zoom"
          :min="25"
          :max="300"
          :step="25"
          :show-tooltip="false"
          @update:model-value="setZoom($event as number)"
        />
        <el-button circle :icon="ZoomIn" aria-label="放大" @click="setZoom(zoom + 25)" />
        <span>{{ zoom }}%</span>
      </div>
    </div>

    <div class="pattern-viewport">
      <img
        :src="activePreview"
        :alt="patternType === 'number' ? '带 MARD 色号的拼豆图纸' : '拼豆纯色块图纸'"
        :class="{ 'fit-to-window': zoom === 100 }"
        :style="zoom === 100 ? undefined : { width: `${zoom}%` }"
      />
    </div>
  </section>
</template>
