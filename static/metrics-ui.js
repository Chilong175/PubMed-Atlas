const metricsFile = document.querySelector('#metricsFile');
const importStatus = document.querySelector('#metricsImportStatus');

function metricsSourceText(info) {
  const sources = { demo: 'Demo 示例表（未经权威来源核验）', publisher: '出版社公开指标', imported: '用户导入指标表' };
  return `${sources[info.data_source] || '本地指标表'} · ${info.journal_count} 种期刊 · 指标年份 ${(info.source_years || [info.source_year]).join('、')}`;
}

function metricSourceHtml(source) {
  try {
    const url = new URL(source);
    if (url.protocol === 'https:' || url.protocol === 'http:') {
      return `<a href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url.hostname)}</a>`;
    }
  } catch (_) {}
  return escapeHtml(source || '本地表未收录');
}

async function refreshMetricsStatus() {
  try {
    const response = await fetch('/api/metrics');
    if (!response.ok) throw new Error('指标表信息暂不可用');
    const info = await response.json();
    document.querySelector('#metricsTableStatus').textContent = metricsSourceText(info);
    document.querySelector('#metricsSourceHint').textContent = info.data_source === 'demo'
      ? '当前使用 Demo 示例指标，未经权威来源核验，仅供演示。'
      : info.data_source === 'publisher'
        ? '出版社公开指标快照；非全量 JCR 数据库。分区按来源披露，未公布时留空；IF 缺失不参与排序。'
        : '当前使用用户导入指标；缺失值不参与排序。';
  } catch (error) {
    document.querySelector('#metricsTableStatus').textContent = error.message;
  }
}

function renderMetricCoverage(info) {
  if (!info) return;
  document.querySelector('#metricsCoverage').textContent = `本次 ${info.total} 篇，${info.matched} 篇已匹配 IF · 覆盖率 ${info.percent}%`;
  document.querySelector('#metricsTableStatus').textContent = metricsSourceText(info);
  const missing = document.querySelector('#unmatchedJournals');
  missing.replaceChildren();
  const label = document.createElement('p');
  label.textContent = info.unmatched_journals.length ? `待补充期刊（${info.unmatched_journals.length} 种）` : '本次文献均已匹配 IF。';
  missing.append(label);
  for (const item of info.unmatched_journals) {
    const row = document.createElement('div');
    row.textContent = `${item.journal} · ${item.count} 篇`;
    missing.append(row);
  }
}

metricsFile.addEventListener('change', async () => {
  const file = metricsFile.files[0];
  if (!file) return;
  let imported = false;
  importStatus.className = 'section-note';
  try {
    if (file.size > 2_000_000) throw new Error('CSV 文件不能超过 2 MB。');
    metricsFile.disabled = true;
    els.searchBtn.disabled = true;
    importStatus.textContent = '正在校验并导入...';
    const csv_text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
    const result = await postJson('/api/metrics/import', { csv_text });
    imported = true;
    importStatus.textContent = `已导入 ${result.journal_count} 种期刊，指标年份 ${result.source_year}。`;
    await refreshMetricsStatus();
    if (state.search) {
      // Recompute metrics using the current articles, without another PubMed/AI request.
      const payload = { articles: state.search.articles };
      const [analysis, top] = await Promise.all([
        postJson('/api/analyze', payload),
        postJson('/api/top-impact', { ...payload, years: 5, limit: 100 }),
      ]);
      state.analysis = analysis;
      state.topImpact = top;
      renderMetrics(); renderCharts(); renderArticles(); renderTopImpact();
    }
  } catch (error) {
    importStatus.className = 'error';
    importStatus.textContent = imported ? `指标已导入，但当前结果刷新失败，请重新检索。${error.message}` : `导入失败，原表未改动：${error.message}`;
  } finally {
    metricsFile.disabled = false;
    els.searchBtn.disabled = false;
    metricsFile.value = '';
  }
});

refreshMetricsStatus();
