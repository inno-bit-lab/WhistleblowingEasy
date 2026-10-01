import {Injectable} from '@angular/core';
import {HashLocationStrategy} from '@angular/common';

const channels: Record<string, string> = {};

export async function initializeChannelRouting(): Promise<void> {
  const slug = window.location.pathname.split('/')[1];
  if (!slug || !/^\/[a-z0-9-]+\/(report|admin|login)(\/|$)/.test(window.location.pathname)) return;
  const response = await fetch('/api/public/channels/' + encodeURIComponent(slug), {credentials: 'same-origin'});
  if (!response.ok) throw new Error('Reporting channel not found');
  const channel = await response.json();
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
