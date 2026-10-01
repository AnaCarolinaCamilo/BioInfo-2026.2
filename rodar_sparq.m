function app = rodar_sparq(sparqRepo, dataFolder)
% RODAR_SPARQ  Abre a GUI do SPARQ já configurada para os .mat exportados pelo notebook.
%
% USO:
%   app = rodar_sparq('D:\TAIL\Bioinfo_2026.2\SPARQ', 'D:\TAIL\Bioinfo_2026.2\SPARQ_input')
%
% ENTRADAS:
%   sparqRepo  = pasta do repositório SPARQ
%   dataFolder = pasta com os .mat exportados (LFP canais x amostras + fs)
%
% Na GUI: selecione cada sessão, marque o início e o fim de um trecho limpo,
% e clique em "Salvar resultados de todas as sessões". Os resultados ficam em
% <dataFolder>\SPARQ_results\...\<stem>_clean.mat.

    if nargin < 2
        error('rodar_sparq:args', 'Uso: rodar_sparq(sparqRepo, dataFolder)');
    end
    if ~isfolder(sparqRepo)
        error('rodar_sparq:repo', 'Pasta do SPARQ não encontrada: %s', sparqRepo);
    end
    if ~isfolder(dataFolder)
        error('rodar_sparq:data', 'Pasta de dados não encontrada: %s', dataFolder);
    end

    addpath(sparqRepo);

    % Formato gerado por sparq_lfp.exportar_para_sparq
    loader.lfpVariable          = "LFP";
    loader.samplingRateVariable = "fs";
    loader.dataOrientation      = "channels-by-samples";
    loader.signalUnits          = "uV";
    loader.signalScale          = 1;

    app = SPARQ_GUI("DataFolder", dataFolder, "LoaderOptions", loader);
end
