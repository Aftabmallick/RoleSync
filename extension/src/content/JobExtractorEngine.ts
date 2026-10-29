// RoleSync Resilient Dynamic ATS Extraction Engine

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
  private static SELECTOR_TIMEOUT_MS = 6000;

  public async extract(): Promise<ExtractedJobDescription> {
    const url = window.location.href;

    if (url.includes('greenhouse.io')) return this.parseTiered('GREENHOUSE');
    if (url.includes('lever.co')) return this.parseTiered('LEVER');
    if (url.includes('myworkdayjobs.com') || url.includes('workday.com')) return this.parseTiered('WORKDAY');
    if (url.includes('linkedin.com')) return this.parseTiered('LINKEDIN');
    if (url.includes('icims.com')) return this.parseTiered('ICIMS');
    if (url.includes('taleo.net')) return this.parseTiered('TALEO');

    return this.parseGenericReadability();
  }

  private async waitForElement(selectors: string[]): Promise<Element | null> {
    const combinedSelector = selectors.join(', ');
    const existing = document.querySelector(combinedSelector);
    if (existing) return existing;

    return new Promise((resolve) => {
      let timeoutId: any;
      const observer = new MutationObserver(() => {
        const el = document.querySelector(combinedSelector);
        if (el) {
          clearTimeout(timeoutId);
          observer.disconnect();
          resolve(el);
        }
      });

      timeoutId = setTimeout(() => {
        observer.disconnect();
        resolve(null);
      }, JobExtractorEngine.SELECTOR_TIMEOUT_MS);

      observer.observe(document.body, { childList: true, subtree: true });
    });
  }

  private async parseTiered(
    provider: 'GREENHOUSE' | 'LEVER' | 'WORKDAY' | 'LINKEDIN' | 'ICIMS' | 'TALEO'
  ): Promise<ExtractedJobDescription> {
    const registry: Record<string, { titles: string[]; bodies: string[]; companies: string[] }> = {
      GREENHOUSE: {
        titles: ['.app-title', 'h1.app-title', 'h1[class*="title"]', '.job-name'],
        bodies: ['#content .job-post', '#content', '#main', 'div.content'],
        companies: ['.company-name', 'span.company-name', 'a.company-name']
      },
      LEVER: {
        titles: ['.posting-headline h2', 'div.posting-headline > h2', 'h2.posting-headline'],
        bodies: ['.posting-page .content', '[data-qa="job-description"]', '.section-page'],
        companies: ['meta[property="og:site_name"]', '.main-header-logo img', 'a.main-header-logo']
      },
      WORKDAY: {
        titles: ['[data-automation-id="jobPostingHeader"]', 'h2.css-12dw570', 'h1[data-automation-id="jobPostingHeader"]'],
        bodies: ['[data-automation-id="jobPostingDescription"]', '.job-description', 'div.css-1k9q2h5'],
        companies: ['[data-automation-id="company"]', 'meta[name="description"]']
      },
      LINKEDIN: {
        titles: ['.job-details-jobs-unified-top-card__job-title', 'h1.t-24', '.topcard__title'],
        bodies: ['#job-details', '.jobs-description__content', '.jobs-box__html-content'],
        companies: ['.job-details-jobs-unified-top-card__company-name a', '.topcard__org-name-link']
      },
      ICIMS: {
        titles: ['.iCIMS_Header', 'h1.iCIMS_JobTitle', '.job-title'],
        bodies: ['.iCIMS_JobContent', '.iCIMS_JobDetails', '.job-description'],
        companies: ['.iCIMS_Company', '.company-name']
      },
      TALEO: {
        titles: ['.titlepage', 'h1.title', '.requisitionDescriptionTitle'],
        bodies: ['.editcontentpane', '#requisitionDescriptionInterface', '.contentpane'],
        companies: ['.companylogo', 'meta[property="og:site_name"]']
      }
    };

    const targetConfig = registry[provider];
    const bodyNode = await this.waitForElement(targetConfig.bodies);

    if (!bodyNode) {
      console.warn(`[RoleSync] Primary selectors timed out for ${provider}. Falling back to heuristic text-density parsing.`);
      return this.parseGenericReadability(provider);
    }

    const titleNode = document.querySelector(targetConfig.titles.join(', '));
    const companyNode = document.querySelector(targetConfig.companies.join(', '));

    let company = '';
    if (companyNode) {
      company = companyNode.tagName === 'META'
        ? (companyNode as HTMLMetaElement).content
        : (companyNode.textContent?.replace(/^at\s+/i, '').trim() || '');
    }

    return {
      atsProvider: provider,
      title: titleNode?.textContent?.trim() || document.title.split(/[-|–]/)[0].trim(),
      company: company || 'Identified Company',
      rawTextContent: this.cleanText(bodyNode.textContent || ''),
      cleanedHtmlContent: bodyNode.innerHTML,
      sourceUrl: window.location.href,
      selectorVersion: '2026.10-v3'
    };
  }

  private parseGenericReadability(provider: any = 'GENERIC'): ExtractedJobDescription {
    // TreeWalker text-density parsing for arbitrary unmapped career portals
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
      if (text.length > 30) {
        candidateNodes.push(text);
      }
    }

    return {
      atsProvider: provider,
      title: document.title.split(/[-|–]/)[0].trim(),
      company: '',
      rawTextContent: candidateNodes.join('\n\n'),
      cleanedHtmlContent: '',
      sourceUrl: window.location.href,
      selectorVersion: 'generic-treewalker-v3'
    };
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
