# VueUse Core 使用方式与配置知识库

> 版本快照：基于 VueUse 官方文档 v14.3.0 整理  
> 用途：中文 RAG / Qdrant / Dify / LangChain / LangGraph 知识库测试  
> 建议切片：按 `## VU-` 二级标题切分  
> 生成日期：2026-07-15

## 文档说明

这份文档不是官方文档的完整复制，而是把 VueUse Core 常见使用方式、配置项、工程实践、典型场景整理成适合 RAG 的中文知识库。

每个 chunk 包含：

- `chunk_id`
- `title`
- `category`
- `tags`
- `difficulty`
- `source`
- 使用场景
- 知识内容
- 代码示例
- 适合提问
- 注意事项

## 官方参考入口

- VueUse 首页：https://vueuse.org/
- Get Started：https://vueuse.org/guide/
- Best Practice：https://vueuse.org/guide/best-practice
- Configurations：https://vueuse.org/guide/config
- Components：https://vueuse.org/guide/components
- Functions：https://vueuse.org/functions

## 导入建议

```yaml
collection: vueuse_core_kb
language: zh-CN
source_type: technical_docs
framework: Vue 3
library: VueUse
version_snapshot: v14.3.0
chunk_strategy: heading_by_VU_id
```

---


## VU-001：VueUse 定位

```yaml
chunk_id: VU-001
title: VueUse 定位
category: 基础
tags: [vueuse, composition-api, vue3]
difficulty: beginner
source: https://vueuse.org/guide/
```

### 使用场景

理解 VueUse 在 Vue 3 项目中的作用。

### 知识内容

VueUse 是基于 Vue Composition API 的工具函数集合，覆盖状态、浏览器 API、元素观察、传感器、网络请求、动画、watch 增强、响应式工具等常见场景。它不是 UI 组件库，也不是完整业务框架，更像是一套可组合的基础 hooks。

### 代码示例

```ts
import { useMouse, useLocalStorage, useDark } from '@vueuse/core'
const { x, y } = useMouse()
const token = useLocalStorage('token', '')
const isDark = useDark()
```

### 适合提问

- VueUse 是什么？
- VueUse 和组件库有什么区别？
- VueUse 是不是状态管理库？

### 注意事项

无特殊注意事项。

---


## VU-002：安装 @vueuse/core

```yaml
chunk_id: VU-002
title: 安装 @vueuse/core
category: 安装配置
tags: [install, npm, pnpm, core]
difficulty: beginner
source: https://vueuse.org/guide/
```

### 使用场景

普通 Vue 3 项目安装 VueUse。

### 知识内容

核心包是 `@vueuse/core`。VueUse v12 起不再支持 Vue 2；Vue 2 项目需要使用 v11.x 或迁移到 Vue 3。

### 代码示例

```bash
npm i @vueuse/core
pnpm add @vueuse/core
yarn add @vueuse/core
```

### 适合提问

- VueUse 怎么安装？
- Vue2 可以用最新版 VueUse 吗？

### 注意事项

无特殊注意事项。

---


## VU-003：Nuxt 中使用 VueUse

```yaml
chunk_id: VU-003
title: Nuxt 中使用 VueUse
category: 安装配置
tags: [nuxt, auto-import, module]
difficulty: intermediate
source: https://vueuse.org/guide/
```

### 使用场景

Nuxt 3 项目希望自动导入 VueUse 函数。

### 知识内容

Nuxt 项目可以安装 `@vueuse/nuxt` 模块。启用后可以在组件中直接使用很多 VueUse 函数，减少显式 import。团队内要约定是否启用自动导入，避免来源不清晰。

### 代码示例

```bash
npx nuxt@latest module add vueuse
# 或
npm i -D @vueuse/nuxt @vueuse/core
```

```ts
export default defineNuxtConfig({
  modules: ['@vueuse/nuxt'],
})
```

### 适合提问

- Nuxt 里怎么用 VueUse？
- 为什么 Nuxt 里不用 import useMouse？

### 注意事项

无特殊注意事项。

---


## VU-004：按需导入与 Tree Shaking

```yaml
chunk_id: VU-004
title: 按需导入与 Tree Shaking
category: 工程规范
tags: [tree-shaking, bundle, import]
difficulty: beginner
source: https://vueuse.org/
```

### 使用场景

控制打包体积并保持依赖清晰。

### 知识内容

VueUse 支持按需导入。推荐从 `@vueuse/core` 导入需要的函数。不要在项目里创建一个导出所有 VueUse 函数的聚合文件，也不要把 VueUse 全量挂到全局对象上。

### 代码示例

```ts
// 推荐
import { useMouse, useWindowSize } from '@vueuse/core'
```

### 适合提问

- VueUse 会不会很大？
- 怎么避免 VueUse 打包体积过大？

### 注意事项

无特殊注意事项。

---


## VU-005：返回值解构规范

```yaml
chunk_id: VU-005
title: 返回值解构规范
category: 最佳实践
tags: [destructure, ref, reactive]
difficulty: beginner
source: https://vueuse.org/guide/best-practice
```

### 使用场景

理解 VueUse 返回对象中的 ref 如何使用。

### 知识内容

很多 VueUse 函数返回由多个 ref 组成的对象，例如 `useMouse()` 返回 `x` 和 `y`。推荐直接解构。如果希望用对象属性风格访问，可以用 Vue 的 `reactive()` 包裹返回值。

### 代码示例

```ts
import { reactive } from 'vue'
import { useMouse } from '@vueuse/core'

const { x, y } = useMouse()
console.log(x.value, y.value)

const mouse = reactive(useMouse())
console.log(mouse.x, mouse.y)
```

### 适合提问

- useMouse 返回值为什么要 .value？
- VueUse 解构会丢响应式吗？

### 注意事项

无特殊注意事项。

---


## VU-006：副作用自动清理

```yaml
chunk_id: VU-006
title: 副作用自动清理
category: 生命周期
tags: [cleanup, unmount, event-listener]
difficulty: intermediate
source: https://vueuse.org/guide/best-practice
```

### 使用场景

组件卸载时自动释放事件监听、计时器、观察器。

### 知识内容

多数 VueUse 函数会随组件生命周期自动清理副作用。比如 `useEventListener` 在组件卸载时会移除事件监听。部分函数返回 `stop`，可手动停止。

### 代码示例

```ts
import { useEventListener } from '@vueuse/core'

const stop = useEventListener(window, 'resize', () => {
  console.log('resize')
})

stop()
```

### 适合提问

- VueUse 会自动 removeEventListener 吗？
- useEventListener 要不要 onUnmounted？

### 注意事项

无特殊注意事项。

---


## VU-007：响应式参数

```yaml
chunk_id: VU-007
title: 响应式参数
category: 最佳实践
tags: [ref, computed, getter, reactive-arguments]
difficulty: intermediate
source: https://vueuse.org/guide/best-practice
```

### 使用场景

函数参数会随响应式状态变化自动更新。

### 知识内容

很多 VueUse 函数接受 ref、computed 或 reactive getter。这样可以把逻辑写成声明式连接，而不是手动 watch 后再调用。

### 代码示例

```ts
import { computed } from 'vue'
import { useDark, useTitle } from '@vueuse/core'

const isDark = useDark()
useTitle(computed(() => isDark.value ? '夜间模式' : '日间模式'))
```

### 适合提问

- VueUse 参数可以传 ref 吗？
- useTitle 可以传 computed 吗？

### 注意事项

无特殊注意事项。

---


## VU-008：Event Filter 配置

```yaml
chunk_id: VU-008
title: Event Filter 配置
category: 配置
tags: [eventFilter, debounceFilter, throttleFilter]
difficulty: intermediate
source: https://vueuse.org/guide/config
```

### 使用场景

限制高频事件更新频率。

### 知识内容

VueUse 提供 Event Filter，用于控制事件或响应式更新触发频率。常见工具有 `debounceFilter`、`throttleFilter`、`pausableFilter`。适合鼠标、滚动、输入、storage 写入等高频场景。

### 代码示例

```ts
import { debounceFilter, throttleFilter, useMouse, useLocalStorage } from '@vueuse/core'

const { x, y } = useMouse({ eventFilter: debounceFilter(100) })

const draft = useLocalStorage('draft', { title: '' }, {
  eventFilter: throttleFilter(1000),
})
```

### 适合提问

- useMouse 怎么防抖？
- eventFilter 是什么？
- useLocalStorage 写入太频繁怎么办？

### 注意事项

无特殊注意事项。

---


## VU-009：flush 时机配置

```yaml
chunk_id: VU-009
title: flush 时机配置
category: 配置
tags: [flush, watch, pre, post, sync]
difficulty: intermediate
source: https://vueuse.org/guide/config
```

### 使用场景

控制 watch-like composable 的触发时机。

### 知识内容

VueUse 的 watch-like 函数通常遵循 Vue watch 的 flush 机制。需要访问更新后的 DOM 时使用 `flush: 'post'`；必须同步触发时使用 `flush: 'sync'`，但要谨慎。

### 代码示例

```ts
import { ref } from 'vue'
import { watchPausable } from '@vueuse/core'

const count = ref(0)
watchPausable(count, () => {
  // updated DOM available
}, { flush: 'post' })
```

### 适合提问

- VueUse 的 flush 怎么配置？
- 什么时候用 flush post？

### 注意事项

无特殊注意事项。

---


## VU-010：Global Dependencies 注入

```yaml
chunk_id: VU-010
title: Global Dependencies 注入
category: SSR 与测试
tags: [window, document, navigator, iframe, test]
difficulty: intermediate
source: https://vueuse.org/guide/config
```

### 使用场景

在 iframe、测试环境或 SSR 兼容场景中指定全局对象。

### 知识内容

访问浏览器 API 的函数通常允许传入 `window`、`document`、`navigator` 等依赖。默认使用当前全局对象。该配置对 iframe、单元测试、WebView、多窗口环境有用。

### 代码示例

```ts
import { useMouse } from '@vueuse/core'

const parentMouse = useMouse({ window: window.parent })
const childMouse = useMouse({ window: iframe.contentWindow })
```

### 适合提问

- VueUse 怎么支持 iframe？
- 测试环境没有 window 怎么办？

### 注意事项

无特殊注意事项。

---


## VU-011：SSR 使用原则

```yaml
chunk_id: VU-011
title: SSR 使用原则
category: SSR 与测试
tags: [ssr, nuxt, window, localStorage]
difficulty: intermediate
source: https://vueuse.org/guide/config
```

### 使用场景

Nuxt 或 SSR 中安全使用 VueUse。

### 知识内容

浏览器 API 只在客户端存在。SSR 项目中涉及 window、document、localStorage、navigator 的逻辑要注意服务端不可用、初始值差异和 hydration 不一致。能延迟到 mounted 的逻辑尽量延迟。

### 代码示例

```ts
import { tryOnMounted, useLocalStorage } from '@vueuse/core'

const token = useLocalStorage('token', '')

tryOnMounted(() => {
  console.log('client only')
})
```

### 适合提问

- Nuxt 中 window is not defined 怎么办？
- useLocalStorage 为什么可能导致 hydration 问题？

### 注意事项

不要在 SSR 首屏直接依赖 localStorage 决定关键 DOM 结构。

---


## VU-012：@vueuse/components

```yaml
chunk_id: VU-012
title: @vueuse/components
category: 安装配置
tags: [components, renderless, directive]
difficulty: intermediate
source: https://vueuse.org/guide/components
```

### 使用场景

使用 renderless component 版本的 composable。

### 知识内容

`@vueuse/components` 提供部分 composable 的组件版本，例如 `OnClickOutside`、`UseMouse`、`UseDark`。适合希望用模板 slot 或组件事件表达逻辑的场景。

### 代码示例

```bash
npm i @vueuse/core @vueuse/components
```

```vue
<script setup>
import { OnClickOutside } from '@vueuse/components'
</script>

<template>
  <OnClickOutside @trigger="close">
    <div>点击外部关闭</div>
  </OnClickOutside>
</template>
```

### 适合提问

- @vueuse/components 是什么？
- OnClickOutside 组件怎么用？

### 注意事项

无特殊注意事项。

---


## VU-013：useLocalStorage

```yaml
chunk_id: VU-013
title: useLocalStorage
category: State
tags: [localStorage, persist]
difficulty: intermediate
source: https://vueuse.org/core/uselocalstorage/
```

### 使用场景

使用 useLocalStorage 处理 State 相关场景。

### 知识内容

把 localStorage 变成响应式 ref，适合用户偏好、表单草稿、低敏感缓存。

### 代码示例

```ts
const prefs = useLocalStorage('prefs', { theme: 'light', pageSize: 20 })
prefs.value.theme = 'dark'
```

### 适合提问

- useLocalStorage 怎么用？
- 什么时候使用 useLocalStorage？

### 注意事项

无特殊注意事项。

---


## VU-014：useSessionStorage

```yaml
chunk_id: VU-014
title: useSessionStorage
category: State
tags: [sessionStorage, tab]
difficulty: intermediate
source: https://vueuse.org/core/usesessionstorage/
```

### 使用场景

使用 useSessionStorage 处理 State 相关场景。

### 知识内容

把 sessionStorage 变成响应式 ref，适合当前标签页会话内的临时状态。

### 代码示例

```ts
const search = useSessionStorage('order-search', { keyword: '', status: 'all' })
```

### 适合提问

- useSessionStorage 怎么用？
- 什么时候使用 useSessionStorage？

### 注意事项

无特殊注意事项。

---


## VU-015：useStorage

```yaml
chunk_id: VU-015
title: useStorage
category: State
tags: [storage, serializer]
difficulty: intermediate
source: https://vueuse.org/core/usestorage/
```

### 使用场景

使用 useStorage 处理 State 相关场景。

### 知识内容

通用 Storage 封装，可指定 localStorage、sessionStorage 或自定义 storage。

### 代码示例

```ts
const count = useStorage('count', 0)
const user = useStorage('user', null, sessionStorage)
```

### 适合提问

- useStorage 怎么用？
- 什么时候使用 useStorage？

### 注意事项

无特殊注意事项。

---


## VU-016：useStorage 自定义序列化

```yaml
chunk_id: VU-016
title: useStorage 自定义序列化
category: State
tags: [serializer, Date]
difficulty: intermediate
source: https://vueuse.org/core/usestorage/
```

### 使用场景

使用 useStorage 自定义序列化 处理 State 相关场景。

### 知识内容

保存 Date、Map、自定义类或兼容旧格式时使用 serializer。

### 代码示例

```ts
const birthday = useStorage('birthday', new Date(), localStorage, {
  serializer: {
    read: v => new Date(v),
    write: v => v.toISOString(),
  },
})
```

### 适合提问

- useStorage 自定义序列化 怎么用？
- 什么时候使用 useStorage 自定义序列化？

### 注意事项

无特殊注意事项。

---


## VU-017：useStorageAsync

```yaml
chunk_id: VU-017
title: useStorageAsync
category: State
tags: [async-storage, indexeddb]
difficulty: intermediate
source: https://vueuse.org/core/usestorageasync/
```

### 使用场景

使用 useStorageAsync 处理 State 相关场景。

### 知识内容

异步存储封装。初始阶段可能先返回默认值，之后才恢复真实存储值。

### 代码示例

```ts
const token = useStorageAsync('access.token', '', asyncStorage)
// token.value 初始可能仍是默认值
```

### 适合提问

- useStorageAsync 怎么用？
- 什么时候使用 useStorageAsync？

### 注意事项

无特殊注意事项。

---


## VU-018：useToggle

```yaml
chunk_id: VU-018
title: useToggle
category: State
tags: [boolean, toggle]
difficulty: intermediate
source: https://vueuse.org/shared/usetoggle/
```

### 使用场景

使用 useToggle 处理 State 相关场景。

### 知识内容

切换布尔 ref，适合弹窗、开关、暗色模式按钮。

### 代码示例

```ts
const visible = ref(false)
const toggleVisible = useToggle(visible)
toggleVisible()
toggleVisible(true)
```

### 适合提问

- useToggle 怎么用？
- 什么时候使用 useToggle？

### 注意事项

无特殊注意事项。

---


## VU-019：createGlobalState

```yaml
chunk_id: VU-019
title: createGlobalState
category: State
tags: [global-state]
difficulty: intermediate
source: https://vueuse.org/shared/createglobalstate/
```

### 使用场景

使用 createGlobalState 处理 State 相关场景。

### 知识内容

轻量全局状态，多个组件调用得到同一份状态。适合小型共享状态。

### 代码示例

```ts
export const useGlobalCounter = createGlobalState(() => {
  const count = ref(0)
  const inc = () => count.value++
  return { count, inc }
})
```

### 适合提问

- createGlobalState 怎么用？
- 什么时候使用 createGlobalState？

### 注意事项

无特殊注意事项。

---


## VU-020：createSharedComposable

```yaml
chunk_id: VU-020
title: createSharedComposable
category: State
tags: [shared-composable, ssr]
difficulty: intermediate
source: https://vueuse.org/shared/createsharedcomposable/
```

### 使用场景

使用 createSharedComposable 处理 State 相关场景。

### 知识内容

让多个组件共享同一个 composable 实例，减少重复监听或重复副作用。

### 代码示例

```ts
export const useSharedMouse = createSharedComposable(() => useMouse())
```

### 适合提问

- createSharedComposable 怎么用？
- 什么时候使用 createSharedComposable？

### 注意事项

无特殊注意事项。

---


## VU-021：createInjectionState

```yaml
chunk_id: VU-021
title: createInjectionState
category: State
tags: [provide, inject]
difficulty: intermediate
source: https://vueuse.org/shared/createinjectionstate/
```

### 使用场景

使用 createInjectionState 处理 State 相关场景。

### 知识内容

封装 provide/inject，适合页面级局部状态、向导流程、复杂组件树上下文。

### 代码示例

```ts
const [useProvideWizard, useWizard] = createInjectionState(() => {
  const step = ref(1)
  return { step, next: () => step.value++ }
})
```

### 适合提问

- createInjectionState 怎么用？
- 什么时候使用 createInjectionState？

### 注意事项

无特殊注意事项。

---


## VU-022：useCounter

```yaml
chunk_id: VU-022
title: useCounter
category: State
tags: [counter, min, max]
difficulty: intermediate
source: https://vueuse.org/shared/usecounter/
```

### 使用场景

使用 useCounter 处理 State 相关场景。

### 知识内容

计数器状态，提供 inc、dec、set、reset，支持边界。

### 代码示例

```ts
const { count, inc, dec, reset } = useCounter(1, { min: 1, max: 10 })
```

### 适合提问

- useCounter 怎么用？
- 什么时候使用 useCounter？

### 注意事项

无特殊注意事项。

---


## VU-023：useCycleList

```yaml
chunk_id: VU-023
title: useCycleList
category: State
tags: [cycle, mode]
difficulty: intermediate
source: https://vueuse.org/core/usecyclelist/
```

### 使用场景

使用 useCycleList 处理 State 相关场景。

### 知识内容

在固定枚举列表中循环切换，如视图模式、主题、排序方式。

### 代码示例

```ts
const { state, next, prev } = useCycleList(['list', 'grid', 'compact'])
```

### 适合提问

- useCycleList 怎么用？
- 什么时候使用 useCycleList？

### 注意事项

无特殊注意事项。

---


## VU-024：useRefHistory

```yaml
chunk_id: VU-024
title: useRefHistory
category: State
tags: [history, undo, redo]
difficulty: intermediate
source: https://vueuse.org/core/userefhistory/
```

### 使用场景

使用 useRefHistory 处理 State 相关场景。

### 知识内容

记录 ref 历史，支持撤销重做。适合编辑器、表单草稿、配置面板。

### 代码示例

```ts
const text = ref('hello')
const { history, undo, redo } = useRefHistory(text)
```

### 适合提问

- useRefHistory 怎么用？
- 什么时候使用 useRefHistory？

### 注意事项

无特殊注意事项。

---


## VU-025：useManualRefHistory

```yaml
chunk_id: VU-025
title: useManualRefHistory
category: State
tags: [history, commit]
difficulty: intermediate
source: https://vueuse.org/core/usemanualrefhistory/
```

### 使用场景

使用 useManualRefHistory 处理 State 相关场景。

### 知识内容

手动提交历史，适合拖拽结束、批量编辑完成后再记录一次。

### 代码示例

```ts
const shape = ref({ x: 0, y: 0 })
const { commit, undo } = useManualRefHistory(shape, { clone: true })
commit()
```

### 适合提问

- useManualRefHistory 怎么用？
- 什么时候使用 useManualRefHistory？

### 注意事项

无特殊注意事项。

---


## VU-026：useMouse

```yaml
chunk_id: VU-026
title: useMouse
category: Sensors
tags: [mouse, x, y]
difficulty: intermediate
source: https://vueuse.org/core/usemouse/
```

### 使用场景

使用 useMouse 处理 Sensors 相关场景。

### 知识内容

获取响应式鼠标坐标。高频场景可配合 eventFilter 限速。

### 代码示例

```ts
const { x, y } = useMouse({ eventFilter: throttleFilter(16) })
```

### 适合提问

- useMouse 怎么用？
- 什么时候使用 useMouse？

### 注意事项

无特殊注意事项。

---


## VU-027：useMouseInElement

```yaml
chunk_id: VU-027
title: useMouseInElement
category: Elements
tags: [mouse, element]
difficulty: intermediate
source: https://vueuse.org/core/usemouseinelement/
```

### 使用场景

使用 useMouseInElement 处理 Elements 相关场景。

### 知识内容

获取鼠标相对某个元素的位置，适合放大镜、卡片光效、画布坐标。

### 代码示例

```ts
const el = useTemplateRef('el')
const { elementX, elementY, isOutside } = useMouseInElement(el)
```

### 适合提问

- useMouseInElement 怎么用？
- 什么时候使用 useMouseInElement？

### 注意事项

无特殊注意事项。

---


## VU-028：useWindowSize

```yaml
chunk_id: VU-028
title: useWindowSize
category: Browser
tags: [window, resize]
difficulty: intermediate
source: https://vueuse.org/core/usewindowsize/
```

### 使用场景

使用 useWindowSize 处理 Browser 相关场景。

### 知识内容

获取响应式窗口宽高。JS 逻辑需要断点判断或图表重绘时使用。

### 代码示例

```ts
const { width, height } = useWindowSize()
const isMobile = computed(() => width.value < 768)
```

### 适合提问

- useWindowSize 怎么用？
- 什么时候使用 useWindowSize？

### 注意事项

无特殊注意事项。

---


## VU-029：useElementSize

```yaml
chunk_id: VU-029
title: useElementSize
category: Elements
tags: [element, ResizeObserver]
difficulty: intermediate
source: https://vueuse.org/core/useelementsize/
```

### 使用场景

使用 useElementSize 处理 Elements 相关场景。

### 知识内容

获取某个元素的响应式宽高，适合容器图表、编辑器、虚拟列表。

### 代码示例

```ts
const box = useTemplateRef('box')
const { width, height } = useElementSize(box)
```

### 适合提问

- useElementSize 怎么用？
- 什么时候使用 useElementSize？

### 注意事项

无特殊注意事项。

---


## VU-030：useResizeObserver

```yaml
chunk_id: VU-030
title: useResizeObserver
category: Elements
tags: [ResizeObserver]
difficulty: intermediate
source: https://vueuse.org/core/useresizeobserver/
```

### 使用场景

使用 useResizeObserver 处理 Elements 相关场景。

### 知识内容

监听元素尺寸变化并执行自定义逻辑。只读宽高时优先用 useElementSize。

### 代码示例

```ts
useResizeObserver(el, ([entry]) => {
  console.log(entry.contentRect.width)
})
```

### 适合提问

- useResizeObserver 怎么用？
- 什么时候使用 useResizeObserver？

### 注意事项

无特殊注意事项。

---


## VU-031：useIntersectionObserver

```yaml
chunk_id: VU-031
title: useIntersectionObserver
category: Elements
tags: [IntersectionObserver, lazy-load]
difficulty: intermediate
source: https://vueuse.org/core/useintersectionobserver/
```

### 使用场景

使用 useIntersectionObserver 处理 Elements 相关场景。

### 知识内容

判断元素是否进入视口，适合懒加载、曝光埋点、进入视口动画。

### 代码示例

```ts
const { stop } = useIntersectionObserver(target, ([entry]) => {
  visible.value = entry?.isIntersecting || false
})
```

### 适合提问

- useIntersectionObserver 怎么用？
- 什么时候使用 useIntersectionObserver？

### 注意事项

无特殊注意事项。

---


## VU-032：useElementVisibility

```yaml
chunk_id: VU-032
title: useElementVisibility
category: Elements
tags: [visibility]
difficulty: intermediate
source: https://vueuse.org/core/useelementvisibility/
```

### 使用场景

使用 useElementVisibility 处理 Elements 相关场景。

### 知识内容

只关心元素是否可见时使用，返回简单布尔状态。

### 代码示例

```ts
const target = useTemplateRef('target')
const isVisible = useElementVisibility(target)
```

### 适合提问

- useElementVisibility 怎么用？
- 什么时候使用 useElementVisibility？

### 注意事项

无特殊注意事项。

---


## VU-033：useMutationObserver

```yaml
chunk_id: VU-033
title: useMutationObserver
category: Elements
tags: [MutationObserver, dom]
difficulty: intermediate
source: https://vueuse.org/core/usemutationobserver/
```

### 使用场景

使用 useMutationObserver 处理 Elements 相关场景。

### 知识内容

监听 DOM 节点增删、属性或文本变化。不要用它替代 Vue 响应式状态。

### 代码示例

```ts
useMutationObserver(target, mutations => console.log(mutations), {
  childList: true,
  subtree: true,
})
```

### 适合提问

- useMutationObserver 怎么用？
- 什么时候使用 useMutationObserver？

### 注意事项

无特殊注意事项。

---


## VU-034：useScroll / useWindowScroll

```yaml
chunk_id: VU-034
title: useScroll / useWindowScroll
category: Elements
tags: [scroll]
difficulty: intermediate
source: https://vueuse.org/core/usescroll/
```

### 使用场景

使用 useScroll / useWindowScroll 处理 Elements 相关场景。

### 知识内容

获取页面或容器滚动位置，适合返回顶部、吸顶、阅读进度。

### 代码示例

```ts
const { y } = useWindowScroll()
function backTop() { y.value = 0 }
```

### 适合提问

- useScroll / useWindowScroll 怎么用？
- 什么时候使用 useScroll / useWindowScroll？

### 注意事项

无特殊注意事项。

---


## VU-035：useInfiniteScroll

```yaml
chunk_id: VU-035
title: useInfiniteScroll
category: Elements
tags: [infinite-scroll, pagination]
difficulty: intermediate
source: https://vueuse.org/core/useinfinitescroll/
```

### 使用场景

使用 useInfiniteScroll 处理 Elements 相关场景。

### 知识内容

滚动到底部自动加载下一页。必须处理 loading、hasMore、防重复请求。

### 代码示例

```ts
useInfiniteScroll(container, async () => {
  if (loading.value || !hasMore.value) return
  loading.value = true
  try { /* load next page */ }
  finally { loading.value = false }
}, { distance: 100 })
```

### 适合提问

- useInfiniteScroll 怎么用？
- 什么时候使用 useInfiniteScroll？

### 注意事项

无特殊注意事项。

---


## VU-036：onClickOutside

```yaml
chunk_id: VU-036
title: onClickOutside
category: Elements
tags: [outside-click, dropdown]
difficulty: intermediate
source: https://vueuse.org/core/onclickoutside/
```

### 使用场景

使用 onClickOutside 处理 Elements 相关场景。

### 知识内容

点击目标元素外部时触发回调，常用于弹窗、下拉菜单、popover。

### 代码示例

```ts
onClickOutside(panel, () => {
  visible.value = false
}, { ignore: [trigger] })
```

### 适合提问

- onClickOutside 怎么用？
- 什么时候使用 onClickOutside？

### 注意事项

无特殊注意事项。

---


## VU-037：useFocus

```yaml
chunk_id: VU-037
title: useFocus
category: Elements
tags: [focus, input]
difficulty: intermediate
source: https://vueuse.org/core/usefocus/
```

### 使用场景

使用 useFocus 处理 Elements 相关场景。

### 知识内容

控制或读取元素焦点状态，适合搜索框自动聚焦、快捷键聚焦。

### 代码示例

```ts
const input = useTemplateRef('input')
const { focused } = useFocus(input)
focused.value = true
```

### 适合提问

- useFocus 怎么用？
- 什么时候使用 useFocus？

### 注意事项

无特殊注意事项。

---


## VU-038：useFocusWithin

```yaml
chunk_id: VU-038
title: useFocusWithin
category: Elements
tags: [focus-within, form]
difficulty: intermediate
source: https://vueuse.org/core/usefocuswithin/
```

### 使用场景

使用 useFocusWithin 处理 Elements 相关场景。

### 知识内容

判断一个区域内部是否有元素处于焦点状态，适合输入组高亮。

### 代码示例

```ts
const group = useTemplateRef('group')
const { focused } = useFocusWithin(group)
```

### 适合提问

- useFocusWithin 怎么用？
- 什么时候使用 useFocusWithin？

### 注意事项

无特殊注意事项。

---


## VU-039：useDraggable

```yaml
chunk_id: VU-039
title: useDraggable
category: Elements
tags: [drag]
difficulty: intermediate
source: https://vueuse.org/core/usedraggable/
```

### 使用场景

使用 useDraggable 处理 Elements 相关场景。

### 知识内容

让元素可拖拽，适合悬浮按钮、调试面板、小窗口。复杂拖拽排序建议用专门库。

### 代码示例

```ts
const el = useTemplateRef('el')
const { x, y, style } = useDraggable(el, {
  initialValue: { x: 40, y: 40 },
})
```

### 适合提问

- useDraggable 怎么用？
- 什么时候使用 useDraggable？

### 注意事项

无特殊注意事项。

---


## VU-040：useDropZone

```yaml
chunk_id: VU-040
title: useDropZone
category: Elements
tags: [drop, file]
difficulty: intermediate
source: https://vueuse.org/core/usedropzone/
```

### 使用场景

使用 useDropZone 处理 Elements 相关场景。

### 知识内容

把元素变成文件拖拽区域，适合文件上传、图片上传、CSV 导入。

### 代码示例

```ts
const { isOverDropZone } = useDropZone(dropZone, {
  onDrop(files) { console.log(files) },
})
```

### 适合提问

- useDropZone 怎么用？
- 什么时候使用 useDropZone？

### 注意事项

无特殊注意事项。

---


## VU-041：useFileDialog

```yaml
chunk_id: VU-041
title: useFileDialog
category: Browser
tags: [file, upload]
difficulty: intermediate
source: https://vueuse.org/core/usefiledialog/
```

### 使用场景

使用 useFileDialog 处理 Browser 相关场景。

### 知识内容

用函数打开系统文件选择器，适合自定义上传按钮。

### 代码示例

```ts
const { files, open, reset, onChange } = useFileDialog({
  accept: 'image/*',
  multiple: false,
})
open()
```

### 适合提问

- useFileDialog 怎么用？
- 什么时候使用 useFileDialog？

### 注意事项

无特殊注意事项。

---


## VU-042：useFullscreen

```yaml
chunk_id: VU-042
title: useFullscreen
category: Browser
tags: [fullscreen]
difficulty: intermediate
source: https://vueuse.org/core/usefullscreen/
```

### 使用场景

使用 useFullscreen 处理 Browser 相关场景。

### 知识内容

控制页面或指定元素进入全屏。通常需要用户手势触发。

### 代码示例

```ts
const target = useTemplateRef('chart')
const { isFullscreen, enter, exit, toggle } = useFullscreen(target)
```

### 适合提问

- useFullscreen 怎么用？
- 什么时候使用 useFullscreen？

### 注意事项

无特殊注意事项。

---


## VU-043：useDocumentVisibility

```yaml
chunk_id: VU-043
title: useDocumentVisibility
category: Browser
tags: [visibilitychange, tab]
difficulty: intermediate
source: https://vueuse.org/core/usedocumentvisibility/
```

### 使用场景

使用 useDocumentVisibility 处理 Browser 相关场景。

### 知识内容

判断标签页是否可见，适合页面隐藏时暂停轮询、动画、视频。

### 代码示例

```ts
const visibility = useDocumentVisibility()
watch(visibility, state => {
  if (state === 'hidden') pause()
})
```

### 适合提问

- useDocumentVisibility 怎么用？
- 什么时候使用 useDocumentVisibility？

### 注意事项

无特殊注意事项。

---


## VU-044：useEventListener

```yaml
chunk_id: VU-044
title: useEventListener
category: Browser
tags: [event, cleanup]
difficulty: intermediate
source: https://vueuse.org/core/useeventlistener/
```

### 使用场景

使用 useEventListener 处理 Browser 相关场景。

### 知识内容

安全注册事件监听并自动清理，适合 resize、keydown、mousemove 等。

### 代码示例

```ts
useEventListener(window, 'keydown', (e) => {
  if (e.key === 'Escape') close()
})
```

### 适合提问

- useEventListener 怎么用？
- 什么时候使用 useEventListener？

### 注意事项

无特殊注意事项。

---


## VU-045：useEventBus

```yaml
chunk_id: VU-045
title: useEventBus
category: Utilities
tags: [event-bus, emit]
difficulty: intermediate
source: https://vueuse.org/core/useeventbus/
```

### 使用场景

使用 useEventBus 处理 Utilities 相关场景。

### 知识内容

轻量事件总线，适合低频跨组件通知。不要用它承载核心业务状态。

### 代码示例

```ts
const bus = useEventBus<{ id: string }>('order-updated')
bus.on(payload => console.log(payload.id))
bus.emit({ id: '123' })
```

### 适合提问

- useEventBus 怎么用？
- 什么时候使用 useEventBus？

### 注意事项

无特殊注意事项。

---


## VU-046：usePreferredDark

```yaml
chunk_id: VU-046
title: usePreferredDark
category: Browser
tags: [dark, media-query]
difficulty: intermediate
source: https://vueuse.org/core/usepreferreddark/
```

### 使用场景

使用 usePreferredDark 处理 Browser 相关场景。

### 知识内容

读取系统是否偏好暗色模式。它只读取偏好，不负责切换 class。

### 代码示例

```ts
const prefersDark = usePreferredDark()
```

### 适合提问

- usePreferredDark 怎么用？
- 什么时候使用 usePreferredDark？

### 注意事项

无特殊注意事项。

---


## VU-047：useDark

```yaml
chunk_id: VU-047
title: useDark
category: Browser
tags: [dark-mode, theme]
difficulty: intermediate
source: https://vueuse.org/core/usedark/
```

### 使用场景

使用 useDark 处理 Browser 相关场景。

### 知识内容

实现暗色模式开关，通常结合系统偏好、存储状态和 HTML class。

### 代码示例

```ts
const isDark = useDark()
const toggleDark = useToggle(isDark)
```

### 适合提问

- useDark 怎么用？
- 什么时候使用 useDark？

### 注意事项

无特殊注意事项。

---


## VU-048：useColorMode

```yaml
chunk_id: VU-048
title: useColorMode
category: Browser
tags: [theme, color-mode]
difficulty: intermediate
source: https://vueuse.org/core/usecolormode/
```

### 使用场景

使用 useColorMode 处理 Browser 相关场景。

### 知识内容

多主题模式管理，适合 light、dark、auto 或自定义主题。

### 代码示例

```ts
const mode = useColorMode({
  modes: { contrast: 'contrast' },
})
mode.value = 'dark'
```

### 适合提问

- useColorMode 怎么用？
- 什么时候使用 useColorMode？

### 注意事项

无特殊注意事项。

---


## VU-049：useCssVar

```yaml
chunk_id: VU-049
title: useCssVar
category: Browser
tags: [css-var, theme]
difficulty: intermediate
source: https://vueuse.org/core/usecssvar/
```

### 使用场景

使用 useCssVar 处理 Browser 相关场景。

### 知识内容

把 CSS 变量映射为响应式 ref，适合主题色、动态样式。

### 代码示例

```ts
const primary = useCssVar('--primary-color')
primary.value = '#1677ff'
```

### 适合提问

- useCssVar 怎么用？
- 什么时候使用 useCssVar？

### 注意事项

无特殊注意事项。

---


## VU-050：useStyleTag

```yaml
chunk_id: VU-050
title: useStyleTag
category: Browser
tags: [style, css]
difficulty: intermediate
source: https://vueuse.org/core/usestyletag/
```

### 使用场景

使用 useStyleTag 处理 Browser 相关场景。

### 知识内容

运行时插入或更新 style 标签。静态样式不建议放这里。

### 代码示例

```ts
const { css, unload } = useStyleTag('.box { border-radius: 8px; }')
css.value = '.box { border-radius: 16px; }'
```

### 适合提问

- useStyleTag 怎么用？
- 什么时候使用 useStyleTag？

### 注意事项

无特殊注意事项。

---


## VU-051：useTitle

```yaml
chunk_id: VU-051
title: useTitle
category: Browser
tags: [document-title]
difficulty: intermediate
source: https://vueuse.org/core/usetitle/
```

### 使用场景

使用 useTitle 处理 Browser 相关场景。

### 知识内容

响应式设置 document.title，可接收字符串、ref、computed 或 getter。

### 代码示例

```ts
useTitle(computed(() => route.meta.title ? `${route.meta.title} - 后台` : '后台'))
```

### 适合提问

- useTitle 怎么用？
- 什么时候使用 useTitle？

### 注意事项

无特殊注意事项。

---


## VU-052：useFavicon

```yaml
chunk_id: VU-052
title: useFavicon
category: Browser
tags: [favicon]
difficulty: intermediate
source: https://vueuse.org/core/usefavicon/
```

### 使用场景

使用 useFavicon 处理 Browser 相关场景。

### 知识内容

动态读取或设置 favicon，适合多品牌、环境标识、未读提醒。

### 代码示例

```ts
const icon = useFavicon()
icon.value = '/icons/dev.ico'
```

### 适合提问

- useFavicon 怎么用？
- 什么时候使用 useFavicon？

### 注意事项

无特殊注意事项。

---


## VU-053：useOnline

```yaml
chunk_id: VU-053
title: useOnline
category: Network
tags: [online, offline]
difficulty: intermediate
source: https://vueuse.org/core/useonline/
```

### 使用场景

使用 useOnline 处理 Network 相关场景。

### 知识内容

读取浏览器在线状态。在线不代表后端服务一定可达。

### 代码示例

```ts
const online = useOnline()
watch(online, v => { if (!v) showOfflineTip() })
```

### 适合提问

- useOnline 怎么用？
- 什么时候使用 useOnline？

### 注意事项

无特殊注意事项。

---


## VU-054：useNetwork

```yaml
chunk_id: VU-054
title: useNetwork
category: Network
tags: [connection, effectiveType]
difficulty: intermediate
source: https://vueuse.org/core/usenetwork/
```

### 使用场景

使用 useNetwork 处理 Network 相关场景。

### 知识内容

读取更丰富的网络信息，如 online、effectiveType、downlink。浏览器支持不完全。

### 代码示例

```ts
const network = useNetwork()
const slow = computed(() => ['slow-2g','2g'].includes(network.effectiveType.value || ''))
```

### 适合提问

- useNetwork 怎么用？
- 什么时候使用 useNetwork？

### 注意事项

无特殊注意事项。

---


## VU-055：useFetch

```yaml
chunk_id: VU-055
title: useFetch
category: Network
tags: [fetch, request]
difficulty: intermediate
source: https://vueuse.org/core/usefetch/
```

### 使用场景

使用 useFetch 处理 Network 相关场景。

### 知识内容

响应式 Fetch API，提供 data、error、isFetching，支持 abort、拦截、自动重新请求。

### 代码示例

```ts
const { data, error, isFetching, execute, abort } = useFetch('/api/user', {
  immediate: false,
}).json()
execute()
```

### 适合提问

- useFetch 怎么用？
- 什么时候使用 useFetch？

### 注意事项

无特殊注意事项。

---


## VU-056：createFetch

```yaml
chunk_id: VU-056
title: createFetch
category: Network
tags: [baseUrl, interceptor, auth]
difficulty: intermediate
source: https://vueuse.org/core/usefetch/
```

### 使用场景

使用 createFetch 处理 Network 相关场景。

### 知识内容

创建预配置 useFetch，统一 baseUrl、headers、token 注入、错误处理。

### 代码示例

```ts
export const useApiFetch = createFetch({
  baseUrl: '/api',
  options: {
    beforeFetch({ options }) {
      options.headers = { ...options.headers, Authorization: `Bearer ${token}` }
      return { options }
    },
  },
})
```

### 适合提问

- createFetch 怎么用？
- 什么时候使用 createFetch？

### 注意事项

无特殊注意事项。

---


## VU-057：useWebSocket

```yaml
chunk_id: VU-057
title: useWebSocket
category: Network
tags: [websocket, realtime]
difficulty: intermediate
source: https://vueuse.org/core/usewebsocket/
```

### 使用场景

使用 useWebSocket 处理 Network 相关场景。

### 知识内容

封装 WebSocket，适合实时消息、通知、协同、行情。要额外设计心跳、重连、消息幂等。

### 代码示例

```ts
const { status, data, send, open, close } = useWebSocket('wss://example.com/ws', {
  autoReconnect: true,
  heartbeat: true,
})
```

### 适合提问

- useWebSocket 怎么用？
- 什么时候使用 useWebSocket？

### 注意事项

无特殊注意事项。

---


## VU-058：useEventSource

```yaml
chunk_id: VU-058
title: useEventSource
category: Network
tags: [sse, event-source]
difficulty: intermediate
source: https://vueuse.org/core/useeventsource/
```

### 使用场景

使用 useEventSource 处理 Network 相关场景。

### 知识内容

封装 SSE，适合 AI 流式输出、任务进度、日志流等单向推送。

### 代码示例

```ts
const { status, data, error, close } = useEventSource('/api/events')
```

### 适合提问

- useEventSource 怎么用？
- 什么时候使用 useEventSource？

### 注意事项

无特殊注意事项。

---


## VU-059：watchDebounced

```yaml
chunk_id: VU-059
title: watchDebounced
category: Watch
tags: [debounce, search]
difficulty: intermediate
source: https://vueuse.org/shared/watchdebounced/
```

### 使用场景

使用 watchDebounced 处理 Watch 相关场景。

### 知识内容

watch 的防抖版本，适合搜索框、筛选条件、自动保存。

### 代码示例

```ts
watchDebounced(keyword, search, { debounce: 500, maxWait: 2000 })
```

### 适合提问

- watchDebounced 怎么用？
- 什么时候使用 watchDebounced？

### 注意事项

无特殊注意事项。

---


## VU-060：watchThrottled

```yaml
chunk_id: VU-060
title: watchThrottled
category: Watch
tags: [throttle, scroll]
difficulty: intermediate
source: https://vueuse.org/shared/watchthrottled/
```

### 使用场景

使用 watchThrottled 处理 Watch 相关场景。

### 知识内容

watch 的节流版本，适合滚动位置、鼠标位置、拖拽位置等高频状态。

### 代码示例

```ts
watchThrottled(scrollY, report, { throttle: 1000 })
```

### 适合提问

- watchThrottled 怎么用？
- 什么时候使用 watchThrottled？

### 注意事项

无特殊注意事项。

---


## VU-061：watchPausable

```yaml
chunk_id: VU-061
title: watchPausable
category: Watch
tags: [pause, resume]
difficulty: intermediate
source: https://vueuse.org/shared/watchpausable/
```

### 使用场景

使用 watchPausable 处理 Watch 相关场景。

### 知识内容

可暂停和恢复的 watch，适合批量更新时暂停副作用。

### 代码示例

```ts
const { pause, resume } = watchPausable(form, autoSave, { deep: true })
pause()
resume()
```

### 适合提问

- watchPausable 怎么用？
- 什么时候使用 watchPausable？

### 注意事项

无特殊注意事项。

---


## VU-062：watchIgnorable

```yaml
chunk_id: VU-062
title: watchIgnorable
category: Watch
tags: [ignoreUpdates]
difficulty: intermediate
source: https://vueuse.org/shared/watchignorable/
```

### 使用场景

使用 watchIgnorable 处理 Watch 相关场景。

### 知识内容

指定某些更新不触发 watcher，适合表单回填、路由同步、避免循环触发。

### 代码示例

```ts
const { ignoreUpdates } = watchIgnorable(keyword, search)
ignoreUpdates(() => { keyword.value = route.query.q as string })
```

### 适合提问

- watchIgnorable 怎么用？
- 什么时候使用 watchIgnorable？

### 注意事项

无特殊注意事项。

---


## VU-063：whenever

```yaml
chunk_id: VU-063
title: whenever
category: Watch
tags: [truthy, condition]
difficulty: intermediate
source: https://vueuse.org/shared/whenever/
```

### 使用场景

使用 whenever 处理 Watch 相关场景。

### 知识内容

当响应式值变成 truthy 时触发回调。适合 token 有值后执行、弹窗打开后加载。

### 代码示例

```ts
whenever(token, () => loadUserInfo())
```

### 适合提问

- whenever 怎么用？
- 什么时候使用 whenever？

### 注意事项

无特殊注意事项。

---


## VU-064：until

```yaml
chunk_id: VU-064
title: until
category: Watch
tags: [await, condition]
difficulty: intermediate
source: https://vueuse.org/shared/until/
```

### 使用场景

使用 until 处理 Watch 相关场景。

### 知识内容

用 Promise 风格等待 ref 满足条件，适合等待 ready、token、异步状态。

### 代码示例

```ts
await until(ready).toBe(true)
```

### 适合提问

- until 怎么用？
- 什么时候使用 until？

### 注意事项

无特殊注意事项。

---


## VU-065：refDebounced

```yaml
chunk_id: VU-065
title: refDebounced
category: Reactivity
tags: [debounced-ref]
difficulty: intermediate
source: https://vueuse.org/shared/refdebounced/
```

### 使用场景

使用 refDebounced 处理 Reactivity 相关场景。

### 知识内容

创建防抖后的 ref。适合搜索参数、预览渲染、过滤条件。

### 代码示例

```ts
const debouncedKeyword = refDebounced(keyword, 500)
```

### 适合提问

- refDebounced 怎么用？
- 什么时候使用 refDebounced？

### 注意事项

无特殊注意事项。

---


## VU-066：refThrottled

```yaml
chunk_id: VU-066
title: refThrottled
category: Reactivity
tags: [throttled-ref]
difficulty: intermediate
source: https://vueuse.org/shared/refthrottled/
```

### 使用场景

使用 refThrottled 处理 Reactivity 相关场景。

### 知识内容

创建节流后的 ref。适合鼠标位置、滚动位置、窗口尺寸展示。

### 代码示例

```ts
const { x } = useMouse()
const throttledX = refThrottled(x, 100)
```

### 适合提问

- refThrottled 怎么用？
- 什么时候使用 refThrottled？

### 注意事项

无特殊注意事项。

---


## VU-067：computedAsync

```yaml
chunk_id: VU-067
title: computedAsync
category: Reactivity
tags: [async, computed]
difficulty: intermediate
source: https://vueuse.org/core/computedasync/
```

### 使用场景

使用 computedAsync 处理 Reactivity 相关场景。

### 知识内容

异步 computed，适合根据响应式参数请求或异步计算。复杂请求仍建议走统一请求层。

### 代码示例

```ts
const user = computedAsync(async () => {
  const res = await fetch(`/api/users/${userId.value}`)
  return res.json()
}, null)
```

### 适合提问

- computedAsync 怎么用？
- 什么时候使用 computedAsync？

### 注意事项

无特殊注意事项。

---


## VU-068：computedWithControl

```yaml
chunk_id: VU-068
title: computedWithControl
category: Reactivity
tags: [computed, manual]
difficulty: intermediate
source: https://vueuse.org/shared/computedwithcontrol/
```

### 使用场景

使用 computedWithControl 处理 Reactivity 相关场景。

### 知识内容

可手动控制重新计算的 computed，适合高级性能控制场景。

### 代码示例

```ts
const doubled = computedWithControl(() => source.value, () => source.value * 2)
doubled.trigger()
```

### 适合提问

- computedWithControl 怎么用？
- 什么时候使用 computedWithControl？

### 注意事项

无特殊注意事项。

---


## VU-069：syncRef

```yaml
chunk_id: VU-069
title: syncRef
category: Reactivity
tags: [sync, ref]
difficulty: intermediate
source: https://vueuse.org/shared/syncref/
```

### 使用场景

使用 syncRef 处理 Reactivity 相关场景。

### 知识内容

同步两个 ref，可单向或双向。要注意数据流复杂度。

### 代码示例

```ts
const stop = syncRef(source, target)
```

### 适合提问

- syncRef 怎么用？
- 什么时候使用 syncRef？

### 注意事项

无特殊注意事项。

---


## VU-070：useVModel

```yaml
chunk_id: VU-070
title: useVModel
category: Component
tags: [v-model, props, emit]
difficulty: intermediate
source: https://vueuse.org/core/usevmodel/
```

### 使用场景

使用 useVModel 处理 Component 相关场景。

### 知识内容

把 props + emit 封装成可写 ref，简化自定义组件 v-model。

### 代码示例

```ts
const value = useVModel(props, 'modelValue', emit)
```

### 适合提问

- useVModel 怎么用？
- 什么时候使用 useVModel？

### 注意事项

无特殊注意事项。

---


## VU-071：useVModels

```yaml
chunk_id: VU-071
title: useVModels
category: Component
tags: [v-models, props, emit]
difficulty: intermediate
source: https://vueuse.org/core/usevmodels/
```

### 使用场景

使用 useVModels 处理 Component 相关场景。

### 知识内容

批量封装多个 v-model 字段。

### 代码示例

```ts
const { title, visible } = useVModels(props, emit)
```

### 适合提问

- useVModels 怎么用？
- 什么时候使用 useVModels？

### 注意事项

无特殊注意事项。

---


## VU-072：useIntervalFn

```yaml
chunk_id: VU-072
title: useIntervalFn
category: Time
tags: [interval, polling]
difficulty: intermediate
source: https://vueuse.org/shared/useintervalfn/
```

### 使用场景

使用 useIntervalFn 处理 Time 相关场景。

### 知识内容

可暂停、恢复的 interval，适合简单轮询、心跳、定时刷新。

### 代码示例

```ts
const { pause, resume, isActive } = useIntervalFn(refresh, 5000)
```

### 适合提问

- useIntervalFn 怎么用？
- 什么时候使用 useIntervalFn？

### 注意事项

无特殊注意事项。

---


## VU-073：useTimeoutFn

```yaml
chunk_id: VU-073
title: useTimeoutFn
category: Time
tags: [timeout, delay]
difficulty: intermediate
source: https://vueuse.org/shared/usetimeoutfn/
```

### 使用场景

使用 useTimeoutFn 处理 Time 相关场景。

### 知识内容

可控制的 timeout，适合 toast 自动关闭、延迟触发。

### 代码示例

```ts
const { start, stop, isPending } = useTimeoutFn(() => done(), 1000)
```

### 适合提问

- useTimeoutFn 怎么用？
- 什么时候使用 useTimeoutFn？

### 注意事项

无特殊注意事项。

---


## VU-074：useTimeoutPoll

```yaml
chunk_id: VU-074
title: useTimeoutPoll
category: Time
tags: [polling, async]
difficulty: intermediate
source: https://vueuse.org/core/usetimeoutpoll/
```

### 使用场景

使用 useTimeoutPoll 处理 Time 相关场景。

### 知识内容

异步轮询。一次执行完成后再安排下一次，避免请求重叠。

### 代码示例

```ts
const { pause, resume } = useTimeoutPoll(async () => {
  await fetchTaskStatus()
}, 3000)
```

### 适合提问

- useTimeoutPoll 怎么用？
- 什么时候使用 useTimeoutPoll？

### 注意事项

无特殊注意事项。

---


## VU-075：useRafFn

```yaml
chunk_id: VU-075
title: useRafFn
category: Animation
tags: [raf, animation]
difficulty: intermediate
source: https://vueuse.org/core/useraffn/
```

### 使用场景

使用 useRafFn 处理 Animation 相关场景。

### 知识内容

requestAnimationFrame 循环，适合动画、视觉计算、可视化。

### 代码示例

```ts
const { pause, resume } = useRafFn(() => {
  frame.value++
})
```

### 适合提问

- useRafFn 怎么用？
- 什么时候使用 useRafFn？

### 注意事项

无特殊注意事项。

---


## VU-076：useNow / useDateFormat

```yaml
chunk_id: VU-076
title: useNow / useDateFormat
category: Time
tags: [date, format]
difficulty: intermediate
source: https://vueuse.org/shared/usenow/
```

### 使用场景

使用 useNow / useDateFormat 处理 Time 相关场景。

### 知识内容

当前时间与日期格式化，适合时钟、更新时间展示。

### 代码示例

```ts
const now = useNow()
const text = useDateFormat(now, 'YYYY-MM-DD HH:mm:ss')
```

### 适合提问

- useNow / useDateFormat 怎么用？
- 什么时候使用 useNow / useDateFormat？

### 注意事项

无特殊注意事项。

---


## VU-077：useClipboard

```yaml
chunk_id: VU-077
title: useClipboard
category: Browser
tags: [clipboard, copy]
difficulty: intermediate
source: https://vueuse.org/core/useclipboard/
```

### 使用场景

使用 useClipboard 处理 Browser 相关场景。

### 知识内容

复制文本到剪贴板。通常需要 HTTPS 或用户手势。

### 代码示例

```ts
const { copy, copied, isSupported } = useClipboard({ copiedDuring: 1500 })
await copy(orderNo)
```

### 适合提问

- useClipboard 怎么用？
- 什么时候使用 useClipboard？

### 注意事项

无特殊注意事项。

---


## VU-078：useMagicKeys

```yaml
chunk_id: VU-078
title: useMagicKeys
category: Sensors
tags: [keyboard, shortcut]
difficulty: intermediate
source: https://vueuse.org/core/usemagickeys/
```

### 使用场景

使用 useMagicKeys 处理 Sensors 相关场景。

### 知识内容

组合快捷键状态，适合命令面板、编辑器快捷键。

### 代码示例

```ts
const keys = useMagicKeys()
whenever(keys['Ctrl+K'], () => openCommandPalette())
```

### 适合提问

- useMagicKeys 怎么用？
- 什么时候使用 useMagicKeys？

### 注意事项

无特殊注意事项。

---


## VU-079：useKeyModifier

```yaml
chunk_id: VU-079
title: useKeyModifier
category: Sensors
tags: [ctrl, shift, alt]
difficulty: intermediate
source: https://vueuse.org/core/usekeymodifier/
```

### 使用场景

使用 useKeyModifier 处理 Sensors 相关场景。

### 知识内容

读取 Ctrl、Shift、Alt、Meta 等修饰键是否按下。

### 代码示例

```ts
const shift = useKeyModifier('Shift')
const ctrl = useKeyModifier('Control')
```

### 适合提问

- useKeyModifier 怎么用？
- 什么时候使用 useKeyModifier？

### 注意事项

无特殊注意事项。

---


## VU-080：usePointer

```yaml
chunk_id: VU-080
title: usePointer
category: Sensors
tags: [pointer, touch, mouse]
difficulty: intermediate
source: https://vueuse.org/core/usepointer/
```

### 使用场景

使用 usePointer 处理 Sensors 相关场景。

### 知识内容

统一处理鼠标、触摸、触控笔等 Pointer Events。

### 代码示例

```ts
const { x, y, pressure, pointerType } = usePointer()
```

### 适合提问

- usePointer 怎么用？
- 什么时候使用 usePointer？

### 注意事项

无特殊注意事项。

---


## VU-081：useSwipe

```yaml
chunk_id: VU-081
title: useSwipe
category: Sensors
tags: [swipe, gesture]
difficulty: intermediate
source: https://vueuse.org/core/useswipe/
```

### 使用场景

使用 useSwipe 处理 Sensors 相关场景。

### 知识内容

移动端滑动手势识别，适合轮播、抽屉、卡片滑动。

### 代码示例

```ts
const { direction, lengthX, lengthY } = useSwipe(target, {
  onSwipeEnd() { console.log(direction.value) },
})
```

### 适合提问

- useSwipe 怎么用？
- 什么时候使用 useSwipe？

### 注意事项

无特殊注意事项。

---


## VU-082：usePermission

```yaml
chunk_id: VU-082
title: usePermission
category: Browser
tags: [permission]
difficulty: intermediate
source: https://vueuse.org/core/usepermission/
```

### 使用场景

使用 usePermission 处理 Browser 相关场景。

### 知识内容

读取浏览器权限状态，如定位、通知、摄像头。仍需处理实际 API 调用失败。

### 代码示例

```ts
const geolocation = usePermission('geolocation')
const notifications = usePermission('notifications')
```

### 适合提问

- usePermission 怎么用？
- 什么时候使用 usePermission？

### 注意事项

无特殊注意事项。

---


## VU-083：useGeolocation

```yaml
chunk_id: VU-083
title: useGeolocation
category: Sensors
tags: [geolocation, gps]
difficulty: intermediate
source: https://vueuse.org/core/usegeolocation/
```

### 使用场景

使用 useGeolocation 处理 Sensors 相关场景。

### 知识内容

获取用户地理位置。需要用户授权，移动端和浏览器差异较大。

### 代码示例

```ts
const { coords, locatedAt, error, resume, pause } = useGeolocation({
  enableHighAccuracy: true,
})
```

### 适合提问

- useGeolocation 怎么用？
- 什么时候使用 useGeolocation？

### 注意事项

无特殊注意事项。

---


## VU-084：usePreferredLanguages

```yaml
chunk_id: VU-084
title: usePreferredLanguages
category: Browser
tags: [language, i18n]
difficulty: intermediate
source: https://vueuse.org/core/usepreferredlanguages/
```

### 使用场景

使用 usePreferredLanguages 处理 Browser 相关场景。

### 知识内容

读取浏览器语言偏好，适合初始化 i18n 语言。用户应可手动切换。

### 代码示例

```ts
const languages = usePreferredLanguages()
```

### 适合提问

- usePreferredLanguages 怎么用？
- 什么时候使用 usePreferredLanguages？

### 注意事项

无特殊注意事项。

---


## VU-085：usePreferredReducedMotion

```yaml
chunk_id: VU-085
title: usePreferredReducedMotion
category: Browser
tags: [a11y, motion]
difficulty: intermediate
source: https://vueuse.org/core/usepreferredreducedmotion/
```

### 使用场景

使用 usePreferredReducedMotion 处理 Browser 相关场景。

### 知识内容

读取用户是否偏好减少动画，用于可访问性优化。

### 代码示例

```ts
const motion = usePreferredReducedMotion()
const enableAnimation = computed(() => motion.value !== 'reduce')
```

### 适合提问

- usePreferredReducedMotion 怎么用？
- 什么时候使用 usePreferredReducedMotion？

### 注意事项

无特殊注意事项。

---


## VU-086：useArrayFilter

```yaml
chunk_id: VU-086
title: useArrayFilter
category: Array
tags: [array, filter]
difficulty: intermediate
source: https://vueuse.org/core/usearrayfilter/
```

### 使用场景

使用 useArrayFilter 处理 Array 相关场景。

### 知识内容

响应式数组过滤，适合小型本地列表。大数据量考虑后端分页或虚拟列表。

### 代码示例

```ts
const filtered = useArrayFilter(list, item => item.name.includes(keyword.value))
```

### 适合提问

- useArrayFilter 怎么用？
- 什么时候使用 useArrayFilter？

### 注意事项

无特殊注意事项。

---


## VU-087：useSorted

```yaml
chunk_id: VU-087
title: useSorted
category: Array
tags: [array, sort]
difficulty: intermediate
source: https://vueuse.org/core/usesorted/
```

### 使用场景

使用 useSorted 处理 Array 相关场景。

### 知识内容

响应式数组排序，适合小型列表和本地表格。

### 代码示例

```ts
const sorted = useSorted(users, (a, b) => b.score - a.score)
```

### 适合提问

- useSorted 怎么用？
- 什么时候使用 useSorted？

### 注意事项

无特殊注意事项。

---


## VU-088：useVirtualList

```yaml
chunk_id: VU-088
title: useVirtualList
category: Component
tags: [virtual-list, performance]
difficulty: intermediate
source: https://vueuse.org/core/usevirtuallist/
```

### 使用场景

使用 useVirtualList 处理 Component 相关场景。

### 知识内容

虚拟列表，只渲染可视区域附近项。适合几千到几万条本地列表。

### 代码示例

```ts
const { list, containerProps, wrapperProps } = useVirtualList(items, {
  itemHeight: 40,
})
```

### 适合提问

- useVirtualList 怎么用？
- 什么时候使用 useVirtualList？

### 注意事项

无特殊注意事项。

---


## VU-089：tryOnMounted / tryOnUnmounted

```yaml
chunk_id: VU-089
title: tryOnMounted / tryOnUnmounted
category: Component
tags: [lifecycle, composable]
difficulty: intermediate
source: https://vueuse.org/shared/tryonmounted/
```

### 使用场景

使用 tryOnMounted / tryOnUnmounted 处理 Component 相关场景。

### 知识内容

自定义 composable 中安全使用生命周期钩子。

### 代码示例

```ts
tryOnMounted(() => init())
tryOnUnmounted(() => cleanup())
```

### 适合提问

- tryOnMounted / tryOnUnmounted 怎么用？
- 什么时候使用 tryOnMounted / tryOnUnmounted？

### 注意事项

无特殊注意事项。

---


## VU-090：搜索框防抖请求

```yaml
chunk_id: VU-090
title: 搜索框防抖请求
category: 实战场景
tags: [search, debounce, watchDebounced]
difficulty: intermediate
source: https://vueuse.org/shared/watchdebounced/
```

### 使用场景

实战问题：搜索框防抖请求。

### 知识内容

用户输入关键词后延迟请求。推荐 `watchDebounced`，避免每次输入都请求接口。

### 代码示例

```ts
watchDebounced(keyword, async (kw) => {
  if (!kw.trim()) return
  list.value = await api.search(kw)
}, { debounce: 500, maxWait: 2000 })
```

### 适合提问

- 搜索框防抖请求怎么做？

### 注意事项

无特殊注意事项。

---


## VU-091：暗色模式完整方案

```yaml
chunk_id: VU-091
title: 暗色模式完整方案
category: 实战场景
tags: [dark-mode, useDark, useColorMode]
difficulty: intermediate
source: https://vueuse.org/core/usedark/
```

### 使用场景

实战问题：暗色模式完整方案。

### 知识内容

二元暗色开关用 `useDark + useToggle`；多主题、auto、contrast 等模式用 `useColorMode`。

### 代码示例

```ts
const isDark = useDark({ selector: 'html', attribute: 'class' })
const toggleDark = useToggle(isDark)
```

### 适合提问

- 暗色模式完整方案怎么做？

### 注意事项

无特殊注意事项。

---


## VU-092：点击外部关闭菜单

```yaml
chunk_id: VU-092
title: 点击外部关闭菜单
category: 实战场景
tags: [onClickOutside, dropdown]
difficulty: intermediate
source: https://vueuse.org/core/onclickoutside/
```

### 使用场景

实战问题：点击外部关闭菜单。

### 知识内容

下拉菜单、弹层、popover 可用 `onClickOutside`。触发按钮在目标外部时使用 `ignore`。

### 代码示例

```ts
onClickOutside(dropdown, () => visible.value = false, {
  ignore: [trigger],
})
```

### 适合提问

- 点击外部关闭菜单怎么做？

### 注意事项

无特殊注意事项。

---


## VU-093：任务进度轮询

```yaml
chunk_id: VU-093
title: 任务进度轮询
category: 实战场景
tags: [polling, useTimeoutPoll, useOnline]
difficulty: intermediate
source: https://vueuse.org/core/usetimeoutpoll/
```

### 使用场景

实战问题：任务进度轮询。

### 知识内容

异步轮询推荐 `useTimeoutPoll`。页面隐藏或断网时可配合 `useDocumentVisibility`、`useOnline` 暂停。

### 代码示例

```ts
const poll = useTimeoutPoll(fetchStatus, 3000)
watch([useDocumentVisibility(), useOnline()], ([v, online]) => {
  v === 'hidden' || !online ? poll.pause() : poll.resume()
})
```

### 适合提问

- 任务进度轮询怎么做？

### 注意事项

无特殊注意事项。

---


## VU-094：表单草稿保存

```yaml
chunk_id: VU-094
title: 表单草稿保存
category: 实战场景
tags: [useLocalStorage, draft, throttleFilter]
difficulty: intermediate
source: https://vueuse.org/core/uselocalstorage/
```

### 使用场景

实战问题：表单草稿保存。

### 知识内容

表单草稿可用 `useLocalStorage`，并使用 `throttleFilter` 限制写入频率。提交成功后清理草稿。

### 代码示例

```ts
const draft = useLocalStorage('article-draft:v1', { title: '', content: '' }, {
  eventFilter: throttleFilter(1000),
  mergeDefaults: true,
})
```

### 适合提问

- 表单草稿保存怎么做？

### 注意事项

无特殊注意事项。

---


## VU-095：图片懒加载与曝光

```yaml
chunk_id: VU-095
title: 图片懒加载与曝光
category: 实战场景
tags: [useIntersectionObserver, lazy-load]
difficulty: intermediate
source: https://vueuse.org/core/useintersectionobserver/
```

### 使用场景

实战问题：图片懒加载与曝光。

### 知识内容

元素进入视口后加载图片并上报曝光。若只需要布尔可见性，可用 `useElementVisibility`。

### 代码示例

```ts
const { stop } = useIntersectionObserver(img, ([entry]) => {
  if (entry?.isIntersecting) {
    loadImage()
    reportExposure()
    stop()
  }
})
```

### 适合提问

- 图片懒加载与曝光怎么做？

### 注意事项

无特殊注意事项。

---


## VU-096：响应式断点

```yaml
chunk_id: VU-096
title: 响应式断点
category: 实战场景
tags: [useBreakpoints, responsive]
difficulty: intermediate
source: https://vueuse.org/core/usebreakpoints/
```

### 使用场景

实战问题：响应式断点。

### 知识内容

样式变化优先 CSS media query；JS 逻辑确实需要断点时使用 `useBreakpoints`。

### 代码示例

```ts
const breakpoints = useBreakpoints({ mobile: 0, tablet: 768, desktop: 1280 })
const isMobile = breakpoints.smaller('tablet')
```

### 适合提问

- 响应式断点怎么做？

### 注意事项

无特殊注意事项。

---


## VU-097：复制成功提示

```yaml
chunk_id: VU-097
title: 复制成功提示
category: 实战场景
tags: [useClipboard, copy]
difficulty: intermediate
source: https://vueuse.org/core/useclipboard/
```

### 使用场景

实战问题：复制成功提示。

### 知识内容

复制文本并显示短暂成功状态可用 `useClipboard` 的 `copied`。不支持时给出降级提示。

### 代码示例

```ts
const { copy, copied, isSupported } = useClipboard({ copiedDuring: 1500 })
if (isSupported.value) await copy(text)
```

### 适合提问

- 复制成功提示怎么做？

### 注意事项

无特殊注意事项。

---


## VU-098：WebSocket 重连与心跳

```yaml
chunk_id: VU-098
title: WebSocket 重连与心跳
category: 实战场景
tags: [useWebSocket, heartbeat]
difficulty: intermediate
source: https://vueuse.org/core/usewebsocket/
```

### 使用场景

实战问题：WebSocket 重连与心跳。

### 知识内容

可用 `useWebSocket` 配置自动重连和心跳。业务可靠性仍需要消息 id、ack、幂等和重试设计。

### 代码示例

```ts
useWebSocket(url, {
  autoReconnect: { retries: 5, delay: 1000 },
  heartbeat: { message: 'ping', interval: 30000 },
})
```

### 适合提问

- WebSocket 重连与心跳怎么做？

### 注意事项

无特殊注意事项。

---


## VU-099：自定义 composable 规范

```yaml
chunk_id: VU-099
title: 自定义 composable 规范
category: 工程规范
tags: [composable, api-design]
difficulty: intermediate
source: https://vueuse.org/guidelines
```

### 使用场景

实战问题：自定义 composable 规范。

### 知识内容

封装自己的 composable 时，建议返回 ref 对象、自动清理副作用、支持响应式参数、提供 stop 或 pause/resume。

### 代码示例

```ts
export function useFeature(target) {
  const active = ref(false)
  const stop = useEventListener(target, 'click', () => active.value = true)
  return { active, stop }
}
```

### 适合提问

- 自定义 composable 规范怎么做？

### 注意事项

无特殊注意事项。

---


## VU-100：RAG 切片建议

```yaml
chunk_id: VU-100
title: RAG 切片建议
category: RAG
tags: [chunking, metadata, qdrant]
difficulty: beginner
source: https://vueuse.org/functions
```

### 使用场景

把本文档导入向量数据库。

### 知识内容

建议按二级标题 `## VU-` 切分。每个 chunk 是一个独立知识单元，包含 metadata、场景、解释、代码、提问样例和注意事项。Qdrant payload 建议保留 `chunk_id`、`title`、`category`、`tags`、`difficulty`、`source`。

### 代码示例

暂无代码示例。

### 适合提问

- 这份文档怎么切 chunk？
- Qdrant payload 怎么设计？

### 注意事项

无特殊注意事项。

---


## VU-101：RAG 测试问题集

```yaml
chunk_id: VU-101
title: RAG 测试问题集
category: RAG
tags: [evaluation, questions]
difficulty: beginner
source: https://vueuse.org/functions
```

### 使用场景

验证召回、rerank 和答案综合能力。

### 知识内容

测试问题：

1. VueUse 怎么安装？
2. Nuxt 中 VueUse 怎么自动导入？
3. useStorage 怎么保存 Date？
4. 搜索框防抖请求用什么？
5. 点击外部关闭菜单怎么做？
6. 暗色模式用 useDark 还是 useColorMode？
7. useFetch 怎么统一 baseUrl 和 token？
8. WebSocket 怎么配置重连和心跳？
9. 页面隐藏时怎么暂停轮询？
10. useIntersectionObserver 和 useElementVisibility 怎么选？
11. VueUse 副作用会自动清理吗？
12. SSR 中使用 localStorage 要注意什么？
13. useBreakpoints 和 CSS media query 怎么选？
14. 自定义 composable 应该遵循什么规范？

### 代码示例

暂无代码示例。

### 适合提问

- 给我 VueUse RAG 测试问题
- 怎么评估 VueUse 知识库？

### 注意事项

无特殊注意事项。

---


## VU-102：函数选择速查表

```yaml
chunk_id: VU-102
title: 函数选择速查表
category: RAG
tags: [cheatsheet, function-selection]
difficulty: beginner
source: https://vueuse.org/functions
```

### 使用场景

根据需求快速选择函数。

### 知识内容

需求到函数：

- 本地持久化：`useLocalStorage`、`useSessionStorage`、`useStorage`
- 异步存储：`useStorageAsync`
- 暗色模式：`useDark`、`useColorMode`
- 鼠标位置：`useMouse`、`useMouseInElement`
- 元素尺寸：`useElementSize`、`useResizeObserver`
- 进入视口：`useIntersectionObserver`、`useElementVisibility`
- 点击外部：`onClickOutside`
- 滚动：`useScroll`、`useInfiniteScroll`
- 请求：`useFetch`、`createFetch`
- 实时连接：`useWebSocket`、`useEventSource`
- 轮询：`useTimeoutPoll`、`useIntervalFn`
- 防抖节流：`watchDebounced`、`watchThrottled`、`refDebounced`、`refThrottled`
- v-model：`useVModel`、`useVModels`
- 轻量全局状态：`createGlobalState`、`createSharedComposable`

### 代码示例

暂无代码示例。

### 适合提问

- VueUse 函数怎么选？
- 给我 VueUse 速查表

### 注意事项

无特殊注意事项。

---


## VU-103：常见误区

```yaml
chunk_id: VU-103
title: 常见误区
category: 工程规范
tags: [pitfalls, architecture]
difficulty: intermediate
source: https://vueuse.org/guidelines
```

### 使用场景

团队大量使用 VueUse 后建立边界。

### 知识内容

VueUse 不是万能业务框架。不要用 `useEventBus` 承载核心业务状态，不要到处绕过统一请求层直接 `useFetch`，不要把所有状态都塞进 `useLocalStorage`，不要在 SSR 首屏强依赖客户端存储，不要用 DOM observer 替代 Vue 响应式状态。

### 代码示例

暂无代码示例。

### 适合提问

- VueUse 可以替代 Pinia 吗？
- 团队使用 VueUse 有哪些误区？

### 注意事项

无特殊注意事项。

---
