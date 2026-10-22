function batch = sparq_auto(sparqRepo, dataFolder, janelaSeg)
% SPARQ_AUTO  Roda o SPARQ em lote escolhendo a referência limpa automaticamente.
%
% USO:
%   batch = sparq_auto('D:\TAIL\Bioinfo_2026.2\SPARQ', 'D:\TAIL\Bioinfo_2026.2\SPARQ_input', 10)
%
% Critério da referência (substitui os dois cliques da GUI):
%   1. A sessão é dividida em janelas de `janelaSeg` segundos (passo de 1 s).
%   2. Para cada canal, o desvio-padrão de cada janela é dividido pela mediana
%      dos desvios-padrão daquele canal (assim todos os canais pesam igual).
%   3. Janelas em que algum canal fica abaixo de 0,2x sua mediana são
%      descartadas (sinal achatado / desconectado / saturado).
%   4. A referência é a janela com menor soma dos desvios normalizados.
%
% Saídas iguais às da GUI: <dataFolder>\SPARQ_results\<subpasta>\<stem>\<stem>_clean.mat,
% imagens em SPARQ_results\imagens\... e o log das referências em
% SPARQ_results\referencias_automaticas.csv. Resultados existentes não são substituídos.

    if nargin < 3 || isempty(janelaSeg)
        janelaSeg = 10;
    end
    addpath(sparqRepo);

    % Formato gerado por sparq_lfp.exportar_para_sparq (igual a rodar_sparq.m)
    config.loader.lfpVariable          = "LFP";
    config.loader.samplingRateVariable = "fs";
    config.loader.samplingRateHz       = [];
    config.loader.timeVariable         = "";
    config.loader.channelLabelsVariable = "";
    config.loader.dataOrientation      = "channels-by-samples";
    config.loader.signalUnits          = "uV";
    config.loader.signalScale          = 1;
    config.excludedChannels = [];
    config.detection = struct('thresholdStd', [], 'minSimultaneousChannels', [], ...
        'mergeGapSamples', [], 'settleWindowSamples', [], 'settleToleranceStd', []);
    config.output.includeConcat = false;
    config.output.includeNaN    = false;
    config.plot.enabled         = true;

    dataRoot   = char(dataFolder);
    outputRoot = fullfile(dataRoot, 'SPARQ_results');
    arquivos = SPARQ.internal.discoverInputFiles(dataRoot, "*.mat", outputRoot);
    if isempty(arquivos)
        error('sparq_auto:semArquivos', 'Nenhum .mat encontrado em %s', dataRoot);
    end

    partes = cell(numel(arquivos), 1);
    for i = 1:numel(arquivos)
        partes{i} = SPARQ.discoverSessions(arquivos(i), ...
            'InputFormat', "auto", 'LoaderOptions', config.loader);
    end
    manifest = vertcat(partes{:});

    % Uma pasta por sessão (como a GUI) e cache de referência ao lado
    for i = 1:height(manifest)
        [pastaFonte, stem] = fileparts(manifest.SourceFile(i));
        relativo = erase(string(pastaFonte), string(dataRoot));
        relativo = regexprep(relativo, '^[\\/]+', '');
        stem = regexprep(stem, '[^A-Za-z0-9_.-]', '_');
        manifest.OutputDirectory(i) = string(fullfile(outputRoot, relativo, stem));
        manifest.ReferenceCacheFile(i) = string(fullfile(outputRoot, ...
            '.reference_cache', relativo, stem + "_reference.mat"));
    end
    manifest.ExcludedChannels = repmat({config.excludedChannels}, height(manifest), 1);
    manifest = SPARQ.validateManifest(manifest);

    referencias = containers.Map();
    seletor = @(session) escolherReferencia(session, janelaSeg, referencias);

    batch = SPARQ.runBatch(manifest, ...
        'Parameters', @(session, row) SPARQ.internal.mainParameters(session, config), ...
        'ResultCallback', @(session, result, params, row) salvarImagens( ...
            session, result, params, row, outputRoot), ...
        'SelectionProvider', seletor, ...
        'SaveResults', true, ...
        'Overwrite', false, ...
        'ContinueOnError', true);

    salvarLogReferencias(batch.report, referencias, janelaSeg, outputRoot);
    disp(batch.report(:, {'SessionId', 'Status', 'PercentNoise', 'ErrorMessage'}));
    fprintf('\n%d/%d sessões processadas. Resultados em %s\n', ...
        nnz(batch.report.Status == "ok"), height(batch.report), outputRoot);
end

% ------------------------------------------------------------------------
function intervalo = escolherReferencia(session, janelaSeg, referencias)
    fs = session.samplingRateHz;
    lfp = double(session.lfp);
    n = size(lfp, 2);
    tamanho = round(janelaSeg * fs);
    passo = round(fs);
    if n <= tamanho
        error('sparq_auto:sessaoCurta', ...
            'Sessão com %.1f s, menor que a janela de %g s.', n / fs, janelaSeg);
    end

    inicios = 1:passo:(n - tamanho + 1);
    desvios = zeros(size(lfp, 1), numel(inicios));
    for k = 1:numel(inicios)
        desvios(:, k) = std(lfp(:, inicios(k):inicios(k) + tamanho - 1), 0, 2);
    end
    normalizado = desvios ./ median(desvios, 2);
    custo = sum(normalizado, 1);
    custo(any(normalizado < 0.2, 1)) = Inf;
    [melhor, k] = min(custo);
    if ~isfinite(melhor)
        error('sparq_auto:semReferencia', 'Nenhuma janela válida para referência.');
    end

    t = session.time;
    intervalo = [t(inicios(k)), t(inicios(k) + tamanho - 1)];
    referencias(char(chaveSessao(session))) = [intervalo, melhor / size(lfp, 1)];
end

% ------------------------------------------------------------------------
function salvarImagens(session, result, params, row, outputRoot)
    SPARQ.internal.plotProcessingResult(session, result, params, 20000);
    SPARQ.internal.savePlotImages(row, outputRoot, false);
end

% ------------------------------------------------------------------------
function salvarLogReferencias(report, referencias, janelaSeg, outputRoot)
    n = height(report);
    inicio = NaN(n, 1); fim = NaN(n, 1); desvioRelativo = NaN(n, 1);
    for i = 1:n
        chave = char(report.SessionId(i));
        if isKey(referencias, chave)
            r = referencias(chave);
            inicio(i) = r(1); fim(i) = r(2); desvioRelativo(i) = r(3);
        end
    end
    log = table(report.SessionId, report.Status, inicio, fim, desvioRelativo, ...
        report.PercentNoise, repmat(janelaSeg, n, 1), ...
        'VariableNames', {'sessao', 'status', 'ref_inicio_s', 'ref_fim_s', ...
        'desvio_relativo_medio', 'pct_ruido', 'janela_s'});
    destino = fullfile(outputRoot, 'referencias_automaticas.csv');
    if isfile(destino)
        antigo = readtable(destino, 'TextType', 'string');
        log = [antigo(~ismember(antigo.sessao, log.sessao(log.status == "ok")), :); ...
               log(log.status == "ok", :)];
    end
    writetable(log, destino);
end

% ------------------------------------------------------------------------
function chave = chaveSessao(session)
    if isfield(session, 'sessionId') && strlength(string(session.sessionId)) > 0
        chave = string(session.sessionId);
    else
        [~, chave] = fileparts(string(session.sourceFile));
    end
end
