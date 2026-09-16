<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Collection, EditPen, House, User } from '@element-plus/icons-vue'

import { useAuthStore } from './stores/auth'

const router = useRouter()
const auth = useAuthStore()

onMounted(async () => {
  await auth.initialize()
  if (!auth.user.value && router.currentRoute.value.meta.requiresAuth) {
    await router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
  }
})

function logout(): void {
  auth.logout()
  void router.push('/login')
}
</script>

<template>
  <div class="site-shell">
    <header class="site-header">
      <RouterLink to="/" class="brand site-brand">
        <div class="brand-mark" aria-hidden="true">
          <span></span><span></span><span></span><span></span>
        </div>
        <div>
          <strong>MARD BEAD LAB</strong>
          <span>拼豆创作社区</span>
        </div>
      </RouterLink>

      <nav class="site-nav" aria-label="主导航">
        <RouterLink to="/"><el-icon><EditPen /></el-icon>创作</RouterLink>
        <RouterLink to="/community"><el-icon><House /></el-icon>社区</RouterLink>
        <RouterLink v-if="auth.user.value" to="/works"><el-icon><Collection /></el-icon>我的作品</RouterLink>
        <RouterLink v-if="auth.user.value" to="/chat"><el-icon><ChatDotRound /></el-icon>聊天</RouterLink>
      </nav>

      <div class="account-nav">
        <template v-if="auth.user.value">
          <span class="account-name"><el-icon><User /></el-icon>{{ auth.user.value.username }}</span>
          <el-button text class="header-button" @click="logout">退出</el-button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="login-link">登录</RouterLink>
          <RouterLink to="/register" class="register-link">注册</RouterLink>
        </template>
      </div>
    </header>
    <RouterView v-slot="{ Component, route }">
      <KeepAlive>
        <component
          :is="Component"
          v-if="route.meta.keepAlive"
          :key="`generator-${auth.user.value?.id || 'guest'}`"
        />
      </KeepAlive>
      <component :is="Component" v-if="!route.meta.keepAlive" />
    </RouterView>
  </div>
</template>
