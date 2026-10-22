function sparq_figuras(sparqRepo, dataFolder, subpasta, pastaSaida)
% SPARQ_FIGURAS  Exporta a figura de sinal bruto do SPARQ de cada sessão.
%
% USO:
%   sparq_figuras('D:\TAIL\Bioinfo_2026.2\SPARQ', 'D:\TAIL\Bioinfo_2026.2\SPARQ_input', ...
%                 'R1', 'D:\TAIL\Bioinfo_2026.2\R1_SPARQ')
%
% Para cada sessão de <dataFolder>\<subpasta> grava <pastaSaida>\<sessão>_sinal_bruto.png:
% a mesma visão de canais empilhados em que a GUI pede o trecho de referência,
% com grade a cada 10 s (marcas menores a cada 1 s) para a escolha da referência
% por especialista. Não processa nem salva resultados do SPARQ.

    addpath(sparqRepo);

    loader.lfpVariable           = "LFP";
    loader.samplingRateVariable  = "fs";
    loader.timeVariable          = "";
    loader.channelLabelsVariable = "";
    loader.dataOrientation       = "channels-by-samples";
    loader.signalUnits           = "uV";
    loader.signalScale           = 1;

    dataRoot = char(dataFolder);
    arquivos = SPARQ.internal.discoverInputFiles( ...
        fullfile(dataRoot, subpasta), "*.mat", fullfile(dataRoot, 'SPARQ_results'));
    if exist(pastaSaida, 'dir') ~= 7
        mkdir(pastaSaida);
    end
    set(groot, 'defaultFigureVisible', 'off');
    restaurar = onCleanup(@() set(groot, 'defaultFigureVisible', 'on'));

    for i = 1:numel(arquivos)
        [~, nome] = fileparts(arquivos(i));
        nome = regexprep(nome, '[^A-Za-z0-9_.-]', '_');
        try
            opcoes = loader;
            opcoes.inputFormat = "auto";
            opcoes.sessionId = string(nome);
            leitor = SPARQ.io.SourceReader(arquivos(i), opcoes);
            session = leitor.load(struct(), opcoes);
            leitor.close();
            params = SPARQ.processingOptions(size(session.lfp, 1));

            fig = figure('Position', [0 0 2400 1400]);
            eixo = axes('Parent', fig);
            SPARQ.viz.channels(session, params, eixo, 'MaxDisplayPoints', 60000);
            set(findall(fig, '-property', 'Interpreter'), 'Interpreter', 'none');
            title(eixo, nome + " - sinal bruto", 'Interpreter', 'none');
            duracao = ceil(session.time(end));
            eixo.XTick = 0:10:duracao;
            eixo.XMinorTick = 'on';
            eixo.XAxis.MinorTickValues = 0:1:duracao;
            eixo.XGrid = 'on';
            eixo.GridColor = [0.6 0.6 0.6];
            eixo.GridAlpha = 0.35;
            eixo.FontSize = 13;
            exportgraphics(fig, fullfile(pastaSaida, nome + "_sinal_bruto.png"), ...
                'Resolution', 150);
            close(fig);
            fprintf('ok     %s\n', nome);
        catch erro
            fprintf('FALHOU %s: %s\n', nome, erro.message);
        end
    end
end
