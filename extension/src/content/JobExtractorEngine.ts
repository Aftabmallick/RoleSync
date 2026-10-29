// RoleSync Resilient Universal Dynamic ATS Extraction Engine

import { TelemetryReporter } from './TelemetryReporter';

export interface ExtractedJobDescription {
  atsProvider: 'GREENHOUSE' | 'LEVER' | 'WORKDAY' | 'LINKEDIN' | 'ICIMS' | 'TALEO' | 'GENERIC';
  title: string;
  company: string;
  rawTextContent: string;
  cleanedHtmlContent: string;
  sourceUrl: string;
  selectorVersion: string;
}

export class JobExtractorEngine {
  private static SELECTOR_TIMEOUT_MS = 3000;

  public async extract(): Promise<ExtractedJobDescription> {
    try {
      const url = window.location.href.toLowerCase();

      // 1. Direct ATS Provider Signatures
      if (url.includes('greenhouse.io')) return await this.parseTiered('GREENHOUSE');
      if (url.includes('lever.co')) return await this.parseTiered('LEVER');
      if (url.includes('myworkdayjobs.com') || url.includes('workday.com')) return await this.parseTiered('WORKDAY');
      if (url.includes('linkedin.com')) return await this.parseTiered('LINKEDIN');
      if (url.includes('icims.com')) return await this.parseTiered('ICIMS');
      if (url.includes('taleo.net')) return await this.parseTiered('TALEO');

      // 2. High-Precision Schema.org JSON-LD Detection (Google Careers, Indeed, ZipRecruiter, Ashby, etc.)
      const jsonLdResult = this.parseJsonLd();
      if (jsonLdResult && jsonLdResult.rawTextContent.length > 80) {
        console.log('[RoleSync] Detected job via Schema.org JobPosting JSON-LD:', jsonLdResult.title);
        return jsonLdResult;
      }

      // 3. Fallback to heuristic text-density & DOM structure parsing
      return this.parseGenericReadability();
    } catch (err) {
      console.warn('[RoleSync] Exception during job extraction, falling back to readability:', err);
      return this.parseGenericReadability();
    }
  }

  /**
   * Universal Schema.org parser for pages with <script type="application/ld+json">
   */
  private parseJsonLd(): ExtractedJobDescription | null {
    try {
      const scripts = document.querySelectorAll('script[type="application/ld+json"]');
      for (const script of Array.from(scripts)) {
        if (!script.textContent) continue;
        try {
          const parsed = JSON.parse(script.textContent);
          const items = Array.isArray(parsed) ? parsed : [parsed];

          for (const item of items) {
            const itemType = item['@type'];
            if (itemType === 'JobPosting' || (Array.isArray(itemType) && itemType.includes('JobPosting'))) {
              const title = item.title || item.name || '';
              const company = item.hiringOrganization?.name || item.hiringOrganization?.legalName || '';
              const rawHtml = item.description || '';

              // Strip HTML tags for clean text
              const tempDiv = document.createElement('div');
              tempDiv.innerHTML = rawHtml;
              const text = tempDiv.textContent || tempDiv.innerText || '';

              if (title && text.length > 50) {
                return {
                  atsProvider: 'GENERIC',
                  title: title.trim(),
                  company: company.trim() || this.detectCompanyFromMeta(),
                  rawTextContent: this.cleanText(text),
                  cleanedHtmlContent: rawHtml,
                  sourceUrl: window.location.href,
                  selectorVersion: 'json-ld-schema-org'
                };
              }
            }
          }
        } catch {
          // Ignore JSON parse errors in individual script tags
        }
      }
    } catch (e) {
      console.warn('[RoleSync] Error parsing JSON-LD:', e);
    }
    return null;
  }

  private async waitForElement(selectors: string[]): Promise<Element | null> {
    for (const sel of selectors) {
      try {
        const found = document.querySelector(sel);
        if (found) return found;
      } catch {
        // ignore malformed selectors
      }
    }

    return new Promise((resolve) => {
      let timeoutId: any;
      const observer = new MutationObserver(() => {
        for (const sel of selectors) {
          try {
            const el = document.querySelector(sel);
            if (el) {
              clearTimeout(timeoutId);
              observer.disconnect();
              resolve(el);
              return;
            }
          } catch {
            // ignore
          }
        }
      });

      timeoutId = setTimeout(() => {
        observer.disconnect();
        resolve(null);
      }, JobExtractorEngine.SELECTOR_TIMEOUT_MS);

      if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
      } else {
        clearTimeout(timeoutId);
        resolve(null);
      }
    });
  }

  private async parseTiered(
    provider: 'GREENHOUSE' | 'LEVER' | 'WORKDAY' | 'LINKEDIN' | 'ICIMS' | 'TALEO'
  ): Promise<ExtractedJobDescription> {
    try {
      const registry: Record<string, { titles: string[]; bodies: string[]; companies: string[] }> = {
        GREENHOUSE: {
          titles: ['.app-title', 'h1.app-title', 'h1[class*="title"]', '.job-name', 'h1'],
          bodies: ['#content .job-post', '#content', '#main', 'div.content', 'article', 'main'],
          companies: ['.company-name', 'span.company-name', 'a.company-name', 'meta[property="og:site_name"]']
        },
        LEVER: {
          titles: ['.posting-headline h2', 'div.posting-headline > h2', 'h2.posting-headline', 'h1'],
          bodies: ['.posting-page .content', '[data-qa="job-description"]', '.section-page', 'main'],
          companies: ['meta[property="og:site_name"]', '.main-header-logo img', 'a.main-header-logo']
        },
        WORKDAY: {
          titles: ['[data-automation-id="jobPostingHeader"]', 'h2.css-12dw570', 'h1[data-automation-id="jobPostingHeader"]', 'h1'],
          bodies: ['[data-automation-id="jobPostingDescription"]', '.job-description', 'div.css-1k9q2h5', '[data-automation-id="job-posting-details"]', 'main'],
          companies: ['[data-automation-id="company"]', 'meta[name="description"]', 'meta[property="og:site_name"]']
        },
        LINKEDIN: {
          titles: [
            '.jobs-search__job-details h1',
            'h1.job-details-jobs-unified-top-card__job-title',
            '.job-details-jobs-unified-top-card__job-title',
            '.jobs-unified-top-card__job-title',
            '.job-details-jobs-unified-top-card__job-title a',
            'h2.job-details-jobs-unified-top-card__job-title',
            '.jobs-details__main-content h1',
            'h1.t-24',
            '.topcard__title',
            'h1.top-card-layout__title',
            'h1'
          ],
          bodies: [
            '.jobs-search__job-details',
            '.job-view-layout',
            '#job-details',
            '.jobs-description__content',
            '.jobs-box__html-content',
            '.jobs-description-content__text',
            '.jobs-description',
            'article.jobs-description',
            '.description__text',
            'article',
            'main'
          ],
          companies: [
            '.job-details-jobs-unified-top-card__company-name a',
            '.job-details-jobs-unified-top-card__company-name',
            '.jobs-unified-top-card__company-name a',
            '.jobs-unified-top-card__company-name',
            '.jobs-unified-top-card__primary-description a',
            '.topcard__org-name-link',
            'a.topcard__org-name-link',
            'a[href*="/company/"]'
          ]
        },
        ICIMS: {
          titles: ['.iCIMS_Header', 'h1.iCIMS_JobTitle', '.job-title', 'h1'],
          bodies: ['.iCIMS_JobContent', '.iCIMS_JobDetails', '.job-description', 'main'],
          companies: ['.iCIMS_Company', '.company-name']
        },
        TALEO: {
          titles: ['.titlepage', 'h1.title', '.requisitionDescriptionTitle', 'h1'],
          bodies: ['.editcontentpane', '#requisitionDescriptionInterface', '.contentpane', 'main'],
          companies: ['.companylogo', 'meta[property="og:site_name"]']
        }
      };

      const targetConfig = registry[provider];
      if (!targetConfig) {
        return this.parseGenericReadability(provider);
      }

      const bodyNode = await this.waitForElement(targetConfig.bodies);

      if (!bodyNode) {
        console.warn(`[RoleSync] Primary selectors timed out for ${provider}. Falling back to heuristic text-density parsing.`);
        TelemetryReporter.reportDrift(provider, targetConfig.bodies).catch(() => {});
        return this.parseGenericReadability(provider);
      }

      let title = '';
      for (const sel of targetConfig.titles) {
        try {
          const el = document.querySelector(sel);
          if (el?.textContent?.trim()) {
            title = el.textContent.trim();
            break;
          }
        } catch {}
      }

      let company = '';
      for (const sel of targetConfig.companies) {
        try {
          const el = document.querySelector(sel);
          if (el) {
            const val = el.tagName === 'META'
              ? (el as HTMLMetaElement).content
              : (el.textContent?.replace(/^at\s+/i, '').trim() || '');
            if (val) {
              company = val;
              break;
            }
          }
        } catch {}
      }

      if (!company) {
        company = this.detectCompanyFromMeta();
      }

      const bodyText = this.cleanText(bodyNode.textContent || '');
      if (bodyText.length < 80) {
        console.warn(`[RoleSync] Body content under 80 chars for ${provider}, falling back to readability.`);
        return this.parseGenericReadability(provider);
      }

      return {
        atsProvider: provider,
        title: title || document.title.split(/[-|–•|]/)[0].trim(),
        company: company || 'Identified Organization',
        rawTextContent: bodyText,
        cleanedHtmlContent: bodyNode.innerHTML,
        sourceUrl: window.location.href,
        selectorVersion: '2026.10-v3'
      };
    } catch (err) {
      console.warn(`[RoleSync] parseTiered error for ${provider}, falling back to readability:`, err);
      return this.parseGenericReadability(provider);
    }
  }

  private parseGenericReadability(provider: any = 'GENERIC'): ExtractedJobDescription {
    // 1. Detect Job Title (h1 or highest-prominence heading)
    const h1 = document.querySelector('h1, [class*="job-title"], [class*="jobTitle"], [data-testid*="job-title"]');
    let title = h1?.textContent?.trim() || '';

    if (!title || title.length > 80) {
      title = document.title.split(/[-|–•|]/)[0].trim();
    }

    // 2. Detect Company
    const company = this.detectCompanyFromMeta();

    // 3. Detect Body Content
    const contentContainer = document.querySelector(
      'main, article, [class*="job-description"], [class*="jobDescription"], [id*="job-description"], [id*="jobDescription"], [class*="content"]'
    );

    let rawText = '';
    let cleanedHtml = '';

    if (contentContainer) {
      rawText = this.cleanText(contentContainer.textContent || '');
      cleanedHtml = contentContainer.innerHTML;
    }

    // Fallback: TreeWalker text density extraction
    if (rawText.length < 150) {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
      const candidateNodes: string[] = [];

      let node: Node | null;
      while ((node = walker.nextNode())) {
        const parent = node.parentElement;
        if (!parent) continue;

        const tag = parent.tagName.toUpperCase();
        if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'NAV', 'HEADER', 'FOOTER', 'SVG', 'BUTTON'].includes(tag)) {
          continue;
        }

        const text = node.textContent?.trim() || '';
        if (text.length > 25) {
          candidateNodes.push(text);
        }
      }
      rawText = candidateNodes.join('\n\n');
    }

    return {
      atsProvider: provider,
      title: title || 'Target Engineering Role',
      company: company || 'Target Organization',
      rawTextContent: this.cleanText(rawText),
      cleanedHtmlContent: cleanedHtml,
      sourceUrl: window.location.href,
      selectorVersion: 'generic-readability-v3'
    };
  }

  private detectCompanyFromMeta(): string {
    const ogSite = document.querySelector('meta[property="og:site_name"]') as HTMLMetaElement;
    if (ogSite?.content?.trim()) return ogSite.content.trim();

    const titleParts = document.title.split(/[-|–•|]/);
    if (titleParts.length >= 2) {
      const lastPart = titleParts[titleParts.length - 1].trim();
      if (lastPart.length < 35 && !lastPart.toLowerCase().includes('jobs') && !lastPart.toLowerCase().includes('careers')) {
        return lastPart;
      }
    }

    // Hostname fallback
    const host = window.location.hostname.replace(/^www\./, '').split('.')[0];
    if (host && host.length > 2) {
      return host.charAt(0).toUpperCase() + host.slice(1);
    }

    return 'Hiring Company';
  }

  private cleanText(raw: string): string {
    return raw
      .replace(/\r\n/g, '\n')
      .replace(/\t/g, ' ')
      .replace(/[ ]{2,}/g, ' ')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }
}
