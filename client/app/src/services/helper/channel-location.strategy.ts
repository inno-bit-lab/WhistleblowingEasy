import {Injectable} from '@angular/core';
import {HashLocationStrategy} from '@angular/common';

const channels: Record<string, string> = {};

export async function initializeChannelRouting(): Promise<void> {
  const slug = window.location.pathname.split('/')[1];
  if (!slug || !/^\/[a-z0-9-]+\/(report|admin|login)(\/|$)/.test(window.location.pathname)) return;
  const response = await fetch('/api/public/channels/' + encodeURIComponent(slug), {credentials: 'same-origin'});
  const body = await response.text();
  if (response.status === 404 || !body.trim()) { showMissingChannel(); return new Promise<void>(() => {}); }
  if (!response.ok) throw new Error('Unable to load reporting channel');
  const channel = JSON.parse(body);
  if (!channel.id || !channel.slug) { showMissingChannel(); return new Promise<void>(() => {}); }
  channels[channel.slug] = channel.id;
}

@Injectable()
export class ChannelLocationStrategy extends HashLocationStrategy {
  private channelSlug = window.location.pathname.split('/')[1];

  override path(includeHash = false): string {
    if (window.location.hash) return super.path(includeHash);
    const parts = window.location.pathname.split('/').filter(Boolean);
    if (!channels[parts[0]]) return super.path(includeHash);
    this.channelSlug = parts[0];
    const route = parts.slice(1).join('/');
    if (route === 'report') {
      const params = new URLSearchParams(window.location.search);
      params.set('context', channels[parts[0]]);
      return '/submission?' + params.toString();
    }
    return '/' + route + window.location.search;
  }

  override prepareExternalUrl(internal: string): string {
    if (!channels[this.channelSlug]) return super.prepareExternalUrl(internal);
    const [route, query = ''] = internal.split('?');
    const params = new URLSearchParams(query);
    if (route === '/submission' && params.get('context') === channels[this.channelSlug]) {
      params.delete('context');
      const extra = params.toString();
      return '/' + this.channelSlug + '/report' + (extra ? '?' + extra : '');
    }
    if (route === '/admin' || route.startsWith('/admin/') || route === '/login' || route.startsWith('/login/passwordreset')) {
      return '/' + this.channelSlug + route + (query ? '?' + query : '');
    }
    return super.prepareExternalUrl(internal);
  }
}

function showMissingChannel(): void {
  const root = document.querySelector('app-root');
  if (!root) return;
  const render = (language: string) => {
    const italian = language === 'it';
    document.documentElement.lang = language;
    document.title = italian ? 'Canale non trovato | Kronos Finance' : 'Channel not found | Kronos Finance';
    const section = document.createElement('section');
    section.className = 'kronos-auth-shell';
    const card = document.createElement('div'); card.className = 'kronos-auth-card';
    const brand = document.createElement('p'); brand.className = 'kronos-page-eyebrow'; brand.textContent = 'Kronos Finance / Whistleblowing';
    const title = document.createElement('h1'); title.textContent = italian ? 'Questo canale non esiste.' : 'This channel does not exist.';
    const description = document.createElement('p'); description.className = 'kronos-page-lead'; description.textContent = italian ? 'Controlla il collegamento ricevuto dalla tua organizzazione oppure torna alla pagina iniziale.' : 'Check the link provided by your organization or return to the homepage.';
    const home = document.createElement('a'); home.className = 'btn btn-primary'; home.href = '/#/'; home.textContent = italian ? 'Torna alla home' : 'Return to homepage';
    const languages = document.createElement('div'); languages.className = 'kronos-missing-languages';
    for (const code of ['it', 'en']) { const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-outline-secondary'; button.textContent = code.toUpperCase(); button.setAttribute('aria-pressed', String(code === language)); button.addEventListener('click', () => { sessionStorage.setItem('language', code); render(code); }); languages.append(button); }
    card.append(brand, title, description, home, languages); section.append(card); root.replaceChildren(section);
  };
  render(sessionStorage.getItem('language') === 'en' ? 'en' : 'it');
}
