<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '', confirmPassword: '' })

async function submit(): Promise<void> {
  if (form.username.length < 3) {
    ElMessage.warning('用户名至少 3 个字符')
    return
  }
  if (form.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    await auth.register({ username: form.username, password: form.password })
    ElMessage.success('注册成功，开始创作吧')
    await router.push('/')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-intro register-intro">
      <p class="eyebrow">JOIN THE COMMUNITY</p>
      <h1>建立你的拼豆作品档案</h1>
      <p>保留历史图纸、随时重新下载，也可以把满意的作品发布给其他创作者。</p>
      <div class="auth-mosaic" aria-hidden="true"><span v-for="item in 24" :key="item"></span></div>
    </section>
    <section class="auth-card">
      <p class="eyebrow">创建账户</p>
      <h2>注册 MARD BEAD LAB</h2>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <input v-model="form.username" class="form-control" maxlength="32" autocomplete="username" placeholder="3–32 位中文、字母、数字或下划线" />
        </el-form-item>
        <el-form-item label="密码">
          <input v-model="form.password" class="form-control" type="password" autocomplete="new-password" placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <input v-model="form.confirmPassword" class="form-control" type="password" autocomplete="new-password" placeholder="再次输入密码" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="auth-submit" @click="submit">创建账户</el-button>
      </el-form>
      <p class="auth-switch">已经注册？<RouterLink to="/login">返回登录</RouterLink></p>
    </section>
  </main>
</template>
