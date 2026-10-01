import {ChannelLocationStrategy, initializeChannelRouting} from '@app/services/helper/channel-location.strategy';
(function() {
  // Limit usage of setAttribute on 'stlyle'
  // This is intended to limit our own libraries to scatter CSP policies violations,
  // it is not intended as a block for an attacker that is already limited by the CSP.
  const originalSetAttribute = Element.prototype.setAttribute;

  Element.prototype.setAttribute = function(name, value) {
    if (name.toLowerCase() !== 'style') {
      originalSetAttribute.call(this, name, value);
    }
  };

  // https://github.com/globaleaks/GlobaLeaks/issues/3277
  // Create a proxy to override localStorage methods with sessionStorage methods
  const localStorageProxy = {
    getItem: (key: string) => sessionStorage.getItem(key),
    setItem: (key: string, value: string) => sessionStorage.setItem(key, value),
    removeItem: (key: string) => sessionStorage.removeItem(key),
    clear: () => sessionStorage.clear(),
    key: (index: number) => sessionStorage.key(index),
    get length() {
      return sessionStorage.length;
    }
  };

  // Assign the proxy to localStorage
  Object.defineProperty(window, 'localStorage', {
    value: localStorageProxy,
    configurable: false,
    writable: false
  });
})();

import '@app/icons';
import { ReceiptValidatorDirective } from "@app/shared/directive/receipt-validator.directive";
import { mockEngine } from "@app/services/helper/mocks";
import { MarkdownRendererService } from '@app/services/helper/markdown.service';
import { TranslatorPipe } from "@app/shared/pipes/translate";
import { TranslateService, TranslateModule } from "@ngx-translate/core";
import { HTTP_INTERCEPTORS, withInterceptorsFromDi, provideHttpClient } from "@angular/common/http";
import { appInterceptor, ErrorCatchingInterceptor, CompletedInterceptor } from "@app/services/root/app-interceptor.service";
import { APP_BASE_HREF, LocationStrategy } from "@angular/common";
import { FlowInjectionToken, NgxFlowModule } from "@flowjs/ngx-flow";
import { NgbDatepickerI18n, NgbModule, NgbPaginationConfig, NgbTooltipConfig, NgbTooltipModule} from "@ng-bootstrap/ng-bootstrap";
import { CustomDatepickerI18n } from "@app/shared/services/custom-datepicker-i18n";
import { appRoutes } from "@app/app.routes";
import { BrowserModule, bootstrapApplication } from "@angular/platform-browser";
import { NgSelectModule } from "@ng-select/ng-select";
import { FormsModule } from "@angular/forms";
import { provideNgIdleKeepalive } from "@ng-idle/keepalive";
import { MarkdownModule, MARKED_OPTIONS } from "ngx-markdown";
import { AppComponent } from "@app/pages/app/app.component";
import { Router, provideRouter } from "@angular/router";
import { ApplicationRef, enableProdMode, importProvidersFrom, provideZonelessChangeDetection } from '@angular/core';
import { provideTranslateHttpLoader } from '@ngx-translate/http-loader';
import Flow from "@flowjs/flow.js";

enableProdMode();

initializeChannelRouting().then(() => bootstrapApplication(AppComponent, {
    providers: [
        provideZonelessChangeDetection(),
        provideRouter(appRoutes),
        provideNgIdleKeepalive(),
        importProvidersFrom(NgbModule,
                            BrowserModule,
                            NgSelectModule,
                            NgxFlowModule,
                            FormsModule,
                            NgbTooltipModule,
                            MarkdownModule.forRoot({
                              markedOptions: {
                                provide: MARKED_OPTIONS,
                                useFactory: (rendererService: MarkdownRendererService) => ({
                                  breaks: true,
                                  renderer: rendererService.getCustomRenderer(),
                                }),
                                deps: [MarkdownRendererService]
                              }
                            }),
                            TranslateModule.forRoot({
                              loader: provideTranslateHttpLoader({prefix:"l10n/", suffix:""}),
                            })),
        { provide: APP_BASE_HREF, useValue: "/" },
        { provide: HTTP_INTERCEPTORS, useClass: appInterceptor, multi: true },
        { provide: HTTP_INTERCEPTORS, useClass: ErrorCatchingInterceptor, multi: true },
        { provide: HTTP_INTERCEPTORS, useClass: CompletedInterceptor, multi: true },
        { provide: FlowInjectionToken, useValue: Flow },
        { provide: LocationStrategy, useClass: ChannelLocationStrategy },
        { provide: NgbDatepickerI18n, useClass: CustomDatepickerI18n },
        {
          provide: NgbPaginationConfig,
          useFactory: () => {
            const config = new NgbPaginationConfig();
            config.size = 'sm';           // Set pagination size (sm for small, lg for large)
            config.boundaryLinks = true;  // Display boundary links (first/last)
            config.directionLinks = true; // Display previous/next buttons
            config.maxSize = 20;          // Maximum number of pages displayed
            config.rotate = true;         // Whether to rotate pages when maxSize > number of pages.
            config.ellipses = true;       // If true, the ellipsis symbols and first/last page numbers
                                          // will be shown when maxSize > number of pages.
            return config;
          }
        },
	{
          provide: NgbTooltipConfig,
          useFactory: () => {
            const config = new NgbTooltipConfig();
	    config.triggers = 'mouseenter:mouseleave';

	    return config;
	  }
        },
        { provide: 'MockEngine', useValue: mockEngine },
        ReceiptValidatorDirective,
        TranslatorPipe,
        TranslateService,
        provideHttpClient(withInterceptorsFromDi())
    ]
})).then(moduleRef => {
    const router = moduleRef.injector.get(Router);
    document.addEventListener('click', event => {
      if (!(event instanceof MouseEvent) || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element)?.closest('a');
      const href = anchor?.getAttribute('href') || '';
      if (anchor?.target === '_blank' || !/^\/[a-z0-9-]+\/(report|admin|login)(\/|$)/.test(window.location.pathname)) return;
      if (/^#\/(admin|login)(\/|$)/.test(href)) {
        event.preventDefault();
        router.navigateByUrl(href.slice(1));
      }
    });
    // Expose Angular stability status to Cypress
    const appRef = moduleRef.injector.get(ApplicationRef);
    (window as any).isAngularStable = () => appRef.isStable;
})
  .catch(err => console.error(err));
