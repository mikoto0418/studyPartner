<template>
  <div class="flex flex-col items-center justify-center w-screen h-screen bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-zinc-50 transition-colors">
    <div class="text-center space-y-4 max-w-sm p-8 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-xl shadow-thin">
      <h1 class="text-4xl font-extrabold text-red-500">403</h1>
      <h2 class="text-lg font-semibold">权限不足</h2>
      <p class="text-xs text-gray-400 dark:text-zinc-500 leading-relaxed">
        抱歉，您没有访问该页面的权限。请使用具备对应权限的账号登录。
      </p>
      <router-link
        to="/login"
        class="inline-block mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded text-xs shadow-sm transition-all"
      >
        返回登录
      </router-link>
    </div>
  </div>
</template>
