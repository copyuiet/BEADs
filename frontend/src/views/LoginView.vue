<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit(): Promise<void> {
  if (!form.username || !form.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form)
    ElMessage.success('欢迎回来')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-intro">
      <p class="eyebrow">WELCOME BACK</p>
      <h1>继续你的拼豆创作</h1>
      <p>登录后自动保存每一次生成结果，在个人作品库中管理并分享到社区。</p>
      <div class="auth-mosaic" aria-hidden="true"><span v-for="item in 24" :key="item"></span></div>
    </section>
    <section class="auth-card">
      <p class="eyebrow">账户登录</p>
      <h2>登录 MARD BEAD LAB</h2>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <input v-model="form.username" class="form-control" maxlength="32" autocomplete="username" placeholder="输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <input v-model="form.password" class="form-control" type="password" autocomplete="current-password" placeholder="至少 8 位" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="auth-submit" @click="submit">登录</el-button>
      </el-form>
      <p class="auth-switch">还没有账户？<RouterLink to="/register">立即注册</RouterLink></p>
    </section>
  </main>
</template>
