<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { MagicStick, Picture, Reading, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { assetUrl, downloadPrivateAsset, fetchPalettes, fetchSpecifications, generatePattern, saveArtwork, uploadImage } from '../api'
import ImageUpload from '../components/ImageUpload.vue'
import PatternPreview from '../components/PatternPreview.vue'
import type {
  ColorMode,
  GenerateResult,
  GridSize,
  PaletteKey,
  PaletteOption,
  PatternType,
  ResizeMode,
  Specification,
  UploadResult,
} from '../types'

const fallbackPalettes: PaletteOption[] = [
  { key: 'mard_221', label: 'MARD 221色', color_count: 221 },
  { key: 'mard_291', label: 'MARD 291色', color_count: 291 },
]
const fallbackSpecifications: Specification[] = [
  { key: '52x52', columns: 52, rows: 52, bead_count: 2704, width_mm: 135.2, height_mm: 135.2 },
  { key: '80x80', columns: 80, rows: 80, bead_count: 6400, width_mm: 208, height_mm: 208 },
  { key: '104x104', columns: 104, rows: 104, bead_count: 10816, width_mm: 270.4, height_mm: 270.4 },
]

const palettes = ref<PaletteOption[]>(fallbackPalettes)
const specifications = ref<Specification[]>(fallbackSpecifications)
const selectedFile = ref<File | null>(null)
const localPreviewUrl = ref('')
const uploadResult = ref<UploadResult | null>(null)
const result = ref<GenerateResult | null>(null)
const uploading = ref(false)
const generating = ref(false)
const saving = ref(false)
const savedJobId = ref('')
const activePattern = ref<PatternType>('number')
const zoom = ref(50)
const resultAnchor = ref<HTMLElement | null>(null)
let autoGenerateTimer: ReturnType<typeof setTimeout> | undefined
let generationSerial = 0

const form = reactive<{
  size: GridSize
  palette: PaletteKey
  colorMode: ColorMode
  dithering: boolean
  patternType: PatternType
  resizeMode: ResizeMode
  contentScale: number
}>({
  size: '52x52',
  palette: 'mard_221',
  colorMode: 'lab',
  dithering: false,
  patternType: 'number',
  resizeMode: 'fit_pad',
  contentScale: 1,
})

const selectedSpecification = computed(
  () => specifications.value.find((item) => item.key === form.size) ?? fallbackSpecifications[0],
)
const previewUrl = computed(() => {
  if (localPreviewUrl.value) return localPreviewUrl.value
  if (uploadResult.value) return assetUrl(uploadResult.value.original_url)
  return ''
})
const canGenerate = computed(() => Boolean(selectedFile.value || uploadResult.value) && !uploading.value)

onMounted(async () => {
  try {
    const [paletteData, specificationData] = await Promise.all([
      fetchPalettes(),
      fetchSpecifications(),
    ])
    palettes.value = paletteData
    specifications.value = specificationData
  } catch {
    // 后端未启动时仍展示固定产品参数，实际生成时会给出明确错误。
  }
})

watch(
  () => [
    form.size,
    form.palette,
    form.colorMode,
    form.dithering,
    form.patternType,
    form.resizeMode,
    form.contentScale,
  ],
  () => scheduleAutoGenerate(),
)

onBeforeUnmount(() => {
  if (autoGenerateTimer) clearTimeout(autoGenerateTimer)
  revokeLocalPreview()
})

async function handleSelected(file: File): Promise<void> {
  revokeLocalPreview()
  selectedFile.value = file
  localPreviewUrl.value = URL.createObjectURL(file)
  uploadResult.value = null
  result.value = null
  savedJobId.value = ''
  const uploaded = await performUpload()
  if (uploaded) scheduleAutoGenerate(0)
}

function handleCleared(): void {
  revokeLocalPreview()
  selectedFile.value = null
  uploadResult.value = null
  result.value = null
  savedJobId.value = ''
  generationSerial += 1
  if (autoGenerateTimer) clearTimeout(autoGenerateTimer)
}

async function performUpload(): Promise<UploadResult | null> {
  if (!selectedFile.value) return uploadResult.value
  uploading.value = true
  try {
    uploadResult.value = await uploadImage(selectedFile.value)
    ElMessage.success('图片已安全上传')
    return uploadResult.value
  } catch (error) {
    uploadResult.value = null
    ElMessage.error(error instanceof Error ? error.message : '图片上传失败')
    return null
  } finally {
    uploading.value = false
  }
}

function scheduleAutoGenerate(delay = 450): void {
  if (!uploadResult.value) return
  if (autoGenerateTimer) clearTimeout(autoGenerateTimer)
  const runId = ++generationSerial
  autoGenerateTimer = setTimeout(() => void generateCurrent(false, runId), delay)
}

async function handleGenerate(): Promise<void> {
  if (autoGenerateTimer) clearTimeout(autoGenerateTimer)
  await generateCurrent(true, ++generationSerial)
}

async function generateCurrent(showSuccess: boolean, runId: number): Promise<void> {
  if (!canGenerate.value) {
    if (showSuccess) ElMessage.warning('请先上传一张 PNG 或 JPG 图片')
    return
  }
  let uploaded = uploadResult.value
  if (!uploaded) uploaded = await performUpload()
  if (!uploaded) return

  generating.value = true
  try {
    const generated = await generatePattern({
      image_id: uploaded.image_id,
      size: form.size,
      palette: form.palette,
      color_mode: form.colorMode,
      dithering: form.dithering,
      pattern_type: form.patternType,
      resize_mode: form.resizeMode,
      content_scale: form.contentScale,
    })
    if (runId !== generationSerial) return
    const firstGeneration = !result.value
    result.value = generated
    savedJobId.value = ''
    activePattern.value = form.patternType
    zoom.value = 50
    await nextTick()
    if (firstGeneration) {
      resultAnchor.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    if (showSuccess) ElMessage.success('拼豆图纸已刷新')
  } catch (error) {
    if (runId === generationSerial) {
      ElMessage.error(error instanceof Error ? error.message : '图纸生成失败')
    }
  } finally {
    if (runId === generationSerial) generating.value = false
  }
}

async function handleSave(): Promise<void> {
  if (!result.value || savedJobId.value === result.value.job_id) return
  saving.value = true
  try {
    const saved = await saveArtwork(result.value.job_id)
    savedJobId.value = saved.job_id
    ElMessage.success('已保存到“我的作品”')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存作品失败')
  } finally {
    saving.value = false
  }
}

async function download(kind: 'png' | 'pdf' | 'csv'): Promise<void> {
  if (!result.value) return
  const path = kind === 'png' ? result.value.png_url : kind === 'pdf' ? result.value.pdf_url : result.value.csv_url
  const filename = kind === 'png' ? 'mard-pattern.png' : kind === 'pdf' ? 'mard-pattern.pdf' : 'materials.csv'
  try {
    await downloadPrivateAsset(path, filename)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文件下载失败')
  }
}

function revokeLocalPreview(): void {
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  localPreviewUrl.value = ''
}
</script>

<template>
  <div class="generator-view">
    <main class="workspace">
      <aside class="control-panel">
        <div class="panel-heading">
          <el-icon><Setting /></el-icon>
          <div>
            <p class="eyebrow">制作参数</p>
            <h1>创建拼豆图纸</h1>
          </div>
        </div>

        <ImageUpload
          :preview-url="previewUrl"
          :uploading="uploading"
          @selected="handleSelected"
          @cleared="handleCleared"
        />

        <el-form class="generator-form" label-position="top">
          <el-form-item label="图纸规格">
            <el-radio-group v-model="form.size" class="size-options">
              <el-radio-button v-for="item in specifications" :key="item.key" :value="item.key">
                {{ item.columns }} × {{ item.rows }}
              </el-radio-button>
            </el-radio-group>
            <div class="spec-summary">
              <span><strong>{{ selectedSpecification.bead_count.toLocaleString() }}</strong> 颗拼豆</span>
              <span>{{ selectedSpecification.width_mm }} × {{ selectedSpecification.height_mm }} mm</span>
            </div>
          </el-form-item>

          <div class="form-grid">
            <el-form-item label="MARD 颜色库">
              <el-select v-model="form.palette" class="full-width">
                <el-option
                  v-for="item in palettes"
                  :key="item.key"
                  :label="item.label"
                  :value="item.key"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="颜色匹配">
              <el-radio-group v-model="form.colorMode">
                <el-radio-button value="lab">Lab</el-radio-button>
                <el-radio-button value="rgb">RGB</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </div>

          <el-form-item label="图片比例">
            <el-radio-group v-model="form.resizeMode" class="full-segment">
              <el-radio-button value="fit_pad">保持比例 · 补白</el-radio-button>
              <el-radio-button value="crop_fill">居中裁剪 · 填满</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="图案占板比例">
            <div class="scale-control">
              <el-slider
                v-model="form.contentScale"
                :min="0.2"
                :max="1"
                :step="0.05"
                :format-tooltip="(value: number) => `${Math.round(value * 100)}%`"
              />
              <strong>{{ Math.round(form.contentScale * 100) }}%</strong>
            </div>
            <div class="field-hint">缩小图案后居中放置，外围保留为空位且不计入用豆。</div>
          </el-form-item>

          <el-form-item label="默认图纸">
            <el-radio-group v-model="form.patternType" class="full-segment">
              <el-radio-button value="color">纯色块</el-radio-button>
              <el-radio-button value="number">MARD 色号</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <div class="switch-row">
            <div>
              <strong>Floyd–Steinberg 误差扩散</strong>
              <span>改善渐变和照片的视觉层次</span>
            </div>
            <el-switch v-model="form.dithering" />
          </div>

          <el-button
            type="primary"
            size="large"
            class="generate-button"
            :icon="MagicStick"
            :loading="generating || uploading"
            :disabled="!canGenerate"
            @click="handleGenerate"
          >
            {{ uploading ? '正在上传' : generating ? '正在自动更新' : '立即刷新图纸' }}
          </el-button>
          <p class="auto-generate-hint">上传及参数调整后会自动生成，无需重复点击。</p>
        </el-form>
      </aside>

      <section class="content-panel">
        <template v-if="result">
          <div ref="resultAnchor" class="scroll-anchor"></div>
          <PatternPreview
            :result="result"
            :original-url="previewUrl"
            :pattern-type="activePattern"
            :zoom="zoom"
            :saved="savedJobId === result.job_id"
            :saving="saving || generating"
            @update:pattern-type="activePattern = $event"
            @update:zoom="zoom = $event"
            @download="download"
            @save="handleSave"
          />

          <section class="statistics-card" aria-labelledby="statistics-title">
            <header class="statistics-heading">
              <div>
                <p class="eyebrow">采购清单</p>
                <h2 id="statistics-title">颜色用量统计</h2>
              </div>
              <span>共使用 {{ result.statistics.length }} 种颜色</span>
            </header>
            <el-table :data="result.statistics" stripe max-height="560" table-layout="fixed">
              <el-table-column label="颜色" width="74">
                <template #default="scope">
                  <span class="color-swatch" :style="{ backgroundColor: scope.row.hex }"></span>
                </template>
              </el-table-column>
              <el-table-column prop="code" label="MARD 色号" min-width="110" sortable />
              <el-table-column prop="hex" label="HEX" min-width="110" />
              <el-table-column prop="count" label="数量" min-width="100" sortable />
              <el-table-column label="占比" min-width="110" sortable prop="percentage">
                <template #default="scope">{{ scope.row.percentage.toFixed(2) }}%</template>
              </el-table-column>
            </el-table>
          </section>
        </template>

        <div v-else class="empty-workspace">
          <div class="empty-grid" aria-hidden="true"></div>
          <div class="empty-icon"><el-icon><Picture /></el-icon></div>
          <p class="eyebrow">等待图片</p>
          <h2>上传图片并选择制作参数</h2>
          <p>生成后可在这里查看色块图、MARD 色号图和材料数量。</p>
          <div class="empty-features">
            <span><el-icon><MagicStick /></el-icon> Lab Delta E 匹配</span>
            <span><el-icon><Reading /></el-icon> A4 矢量 PDF</span>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
