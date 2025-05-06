Teste de client BLE para o Contato01 (Para substituir o ESPNOW)

cd até essa pasta e execute:

python . scan.py para scanear dispositivos BLE próximos

python . --name Contato01 --config-path repertorio/descontato/jessica_e.json  
OU  
python . --address {endereço MAC do dispositivo} --config-path repertorio/descontato/jessica_e.json