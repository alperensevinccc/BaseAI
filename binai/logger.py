import logging
import sys
import coloredlogs
import config

def setup_logger():
    # BaseAI standardına uygun, hem dosyaya hem konsola yazan logger
    
    logger = logging.getLogger("BinAI")
    
    # Mevcut handler'ları temizle (tekrar çağrılma durumuna karşı)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(config.LOG_LEVEL)

    # Konsol Handler (Renkli)
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    coloredlogs.install(level=config.LOG_LEVEL, logger=logger, fmt=console_format, stream=sys.stdout)

    # Dosya Handler (Renksiz)
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_format)

    logger.addHandler(file_handler)
    
    # 'coloredlogs' kendi handler'ını eklediği için ayrıca eklemeye gerek yok
    # ancak file_handler'ı manuel eklemeliyiz.
    
    return logger

log = setup_logger()