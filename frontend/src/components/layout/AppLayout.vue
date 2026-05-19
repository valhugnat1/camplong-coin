<template>
  <div class="app-shell">
    <header class="topbar">
      <TopBar />
      <Ticker />
      <TabNav />
    </header>
    <slot />
  </div>
</template>

<script setup>
import TopBar from './TopBar.vue'
import Ticker from './Ticker.vue'
import TabNav from './TabNav.vue'
</script>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(7, 7, 10, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
</style>
