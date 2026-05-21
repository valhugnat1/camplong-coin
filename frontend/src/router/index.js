import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const routes = [
  { path: "/", redirect: "/wallet" },

  {
    path: "/login",
    name: "login",
    component: () => import("@/views/LoginView.vue"),
    meta: { guest: "user" }, // route publique côté user
  },

  // ─── User (auth requise) ──────────────────────────────────
  {
    path: "/wallet",
    name: "wallet",
    component: () => import("@/views/WalletView.vue"),
    meta: { needsUser: true },
  },

  // Paris : liste + création + détail (remplacent ParisView placeholder)
  {
    path: "/paris",
    name: "paris-list",
    component: () => import("@/views/paris/ParisListView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/paris/new",
    name: "paris-create",
    component: () => import("@/views/paris/ParisCreateView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/paris/:id",
    name: "paris-detail",
    component: () => import("@/views/paris/ParisDetailView.vue"),
    meta: { needsUser: true },
    props: true,
  },

  {
    path: "/casino",
    name: "casino",
    component: () => import("@/views/CasinoView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/milk",
    name: "milk",
    component: () => import("@/views/MilkView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/profile",
    name: "profile",
    component: () => import("@/views/ProfileView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/self-custody",
    name: "self-custody",
    component: () => import("@/views/SelfCustodyView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/buy",
    name: "buy",
    component: () => import("@/views/BuyCampView.vue"),
    meta: { needsUser: true },
  },
  {
    path: "/orders",
    name: "orders",
    component: () => import("@/views/OrdersView.vue"),
    meta: { needsUser: true },
  },

  // ─── Admin ────────────────────────────────────────────────
  {
    path: "/admin/login",
    name: "admin-login",
    component: () => import("@/views/admin/AdminLoginView.vue"),
    meta: { guest: "admin" }, // route publique côté admin
  },
  {
    path: "/admin",
    name: "admin",
    component: () => import("@/views/admin/AdminView.vue"),
    meta: { needsAdmin: true },
  },
  {
    path: "/admin/orders",
    name: "admin-orders",
    component: () => import("@/views/admin/AdminOrdersView.vue"),
    meta: { needsAdmin: true },
  },
  {
    path: "/admin/bets",
    name: "admin-bets",
    component: () => import("@/views/admin/AdminBetsView.vue"),
    meta: { needsAdmin: true },
  },

  // Fallback : 404 → redirect intelligent côté guard
  { path: "/:pathMatch(.*)*", redirect: "/wallet" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

/**
 * Guard global :
 *  1. Routes user (needsUser) : si pas connecté → /login en gardant l'URL voulue
 *     en query (?redirect=…) pour pouvoir y revenir après login.
 *  2. Routes admin (needsAdmin) : pareil, vers /admin/login.
 *  3. Routes guest : si déjà connecté, on bypass le login (UX naturelle).
 */
router.beforeEach((to) => {
  const auth = useAuthStore();

  // 1. Route user qui exige une auth user
  if (to.meta.needsUser && !auth.userToken) {
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  // 2. Route admin qui exige une auth admin
  if (to.meta.needsAdmin && !auth.adminToken) {
    return {
      name: "admin-login",
      query: { redirect: to.fullPath },
    };
  }

  // 3. Page de login déjà connecté → bypass vers le dashboard correspondant
  if (to.meta.guest === "user" && auth.userToken) {
    return { name: "wallet" };
  }
  if (to.meta.guest === "admin" && auth.adminToken) {
    return { name: "admin" };
  }

  return true;
});

export default router;
