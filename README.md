# Carreiro Auto Peças — Landing Page

Landing page "link-in-bio" da **Carreiro Auto Peças**, rede com 5 lojas entre o Ceará e o Piauí. A página substitui o Linktree da empresa por uma experiência própria, rápida e focada em conversão via WhatsApp.

🔗 **Site:** em breve na Netlify

## O que a página tem

- **Hero com vídeo de fundo** e botões de WhatsApp para cada uma das 5 filiais, com mensagem pré-preenchida
- **Motor 3D interativo** — um motor 4 cilindros desenhado em Canvas 2D puro (sem Three.js) que monta conforme o usuário rola a página e pode ser girado com o mouse ou o dedo
- **Seção "Quem Somos"** com foto da equipe
- **Grid de benefícios** (estoque, garantia, entrega, atendimento)
- **Cards das 5 lojas** com endereço, WhatsApp e link para o Google Maps
- **FAQ** em accordion
- Botão flutuante de WhatsApp, toast de "link copiado" e suporte a `prefers-reduced-motion`

## Tecnologias

- HTML, CSS e JavaScript puros — **um único arquivo** `index.html`, sem dependências nem build
- Canvas 2D com projeção 3D própria (rotação por matrizes + slider-crank real para a cinemática dos pistões)
- Google Fonts (Outfit + Inter)

## Estrutura

```
├── index.html          # página completa (HTML + CSS + JS)
└── assets/
    ├── hero.mp4        # vídeo de fundo do hero
    ├── logo.png        # logo da marca
    └── equipe.jpg      # foto da equipe
```

## Rodando localmente

É só abrir o `index.html` no navegador — não precisa de servidor nem instalação.

## Deploy

Site estático puro: qualquer host serve (Netlify, Vercel, GitHub Pages). Na Netlify, basta apontar para a raiz do repositório, sem comando de build.
