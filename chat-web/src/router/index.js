import { createRouter, createWebHistory } from 'vue-router'
import ChatRAG from '../views/ChatRAG.vue'
import ChatAgent from '../views/ChatAgent.vue'

const routes = [
  {
    path: '/',
    name: 'rag',
    component: ChatRAG,
    meta: { title: 'RAG 智能问答' },
  },
  {
    path: '/agent',
    name: 'agent',
    component: ChatAgent,
    meta: { title: 'Agent 智能对话' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
