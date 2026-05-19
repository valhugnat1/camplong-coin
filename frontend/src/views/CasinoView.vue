<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="casino-hero">
        <h2>La maison gagne toujours. <span class="gold">Sauf en CAMP.</span></h2>
        <p>
          Roulette, slots, poker. Les jeux arrivent. En attendant, économise pour pouvoir tout perdre.
          <span class="dim">(disclaimer obligatoire : jouer rend pauvre. sauf si tu gagnes.)</span>
        </p>
      </div>

      <div class="casino-grid">
        <article v-for="(g, i) in games" :key="i" class="game-tile">
          <div>
            <div class="icon">{{ g.icon }}</div>
            <h3>{{ g.name }}</h3>
            <div class="desc">{{ g.desc }}</div>
          </div>
          <div class="game-footer">
            <span class="coming-soon-badge">bientôt</span>
            <span class="mono">RTP {{ g.rtp }}%</span>
          </div>
        </article>
      </div>

      <div class="card friend-tip">
        <div>
          <b style="color: var(--text-0)">Conseil d'ami :</b> mise petit, gagne petit, perds petit.
        </div>
        <div class="signed">— signé : les statistiques</div>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'

const games = [
  { icon: '🎰', name: 'Slots',         desc: '3 rouleaux, des emojis, du regret. Le classique.',      rtp: 96.2 },
  { icon: '🎡', name: 'Roulette',      desc: 'Rouge ou noir. Pair ou impair. Toi ou personne.',       rtp: 97.3 },
  { icon: '🃏', name: 'Poker (Texas)', desc: 'Bluffe tes potes. Ruine-toi en famille.',               rtp: 100  },
  { icon: '🎲', name: 'Dés',           desc: 'Tu mises sur un nombre. Ça tombe. Ou pas.',             rtp: 99.0 },
  { icon: '🪙', name: 'Coinflip',      desc: 'Pile ou face. Pas plus simple. Pas moins addictif.',    rtp: 98.0 },
  { icon: '💥', name: 'Crash',         desc: 'La fusée décolle. Tu sors quand ? Spoiler : trop tard.', rtp: 99.0 }
]
</script>

<style scoped>
.casino-hero {
  background:
    radial-gradient(circle at 80% 50%, rgba(245, 200, 66, 0.12), transparent 60%),
    radial-gradient(circle at 20% 50%, rgba(255, 69, 102, 0.1), transparent 60%),
    linear-gradient(135deg, #14101a 0%, #0d0d14 100%);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 2.4em 2em;
  margin-bottom: 1.5em;
  position: relative;
  overflow: hidden;
}
.casino-hero h2 {
  font-size: 2.4em;
  margin-bottom: 0.3em;
  line-height: 1.05;
  letter-spacing: -0.03em;
  max-width: 16ch;
}
.casino-hero .gold {
  background: linear-gradient(90deg, var(--gold), #ff9700);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.casino-hero p {
  color: var(--text-1);
  max-width: 50ch;
  font-size: 1.02em;
  margin: 0;
}
.casino-hero .dim {
  color: var(--text-2);
  font-style: italic;
}
.casino-hero::after {
  content: '🎰';
  position: absolute;
  right: -10px;
  bottom: -40px;
  font-size: 10em;
  opacity: 0.15;
  transform: rotate(-12deg);
  pointer-events: none;
}

.casino-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1em;
}

.game-tile {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.5em 1.2em;
  min-height: 200px;
  overflow: hidden;
  transition: transform 0.2s, border-color 0.2s;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.game-tile:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
}
.game-tile .icon {
  font-size: 3em;
  line-height: 1;
  margin-bottom: 0.5em;
  filter: drop-shadow(0 4px 14px rgba(255, 122, 0, 0.3));
}
.game-tile h3 {
  font-size: 1.2em;
  margin-bottom: 0.2em;
}
.game-tile .desc {
  color: var(--text-2);
  font-size: 0.85em;
  line-height: 1.4;
}
.game-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 1em;
  font-size: 0.78em;
  color: var(--text-3);
}

.friend-tip {
  margin-top: 1.5em;
  text-align: center;
  color: var(--text-2);
  font-size: 0.92em;
}
.signed {
  color: var(--text-3);
  font-style: italic;
  margin-top: 0.3em;
}

@media (max-width: 640px) {
  .casino-hero { padding: 1.6em 1.3em; }
  .casino-hero h2 { font-size: 1.7em; }
}
</style>
