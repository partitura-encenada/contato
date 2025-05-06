import rtmidi
import argparse
import asyncio # biblioteca bleak requer asyncio
import time
import json

from bleak import BleakClient, BleakScanner # biblioteca de BLE
from bleak.backends.characteristic import BleakGATTCharacteristic

# Consultar no código embarcado
TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e'

class Player:
    def __init__(self):
        self.midiout = None
        self.config = None

        # Sistema de flag assegura que condicionais só executem em mudanças de estado
        self.touch_flag = False
        self.accel_flag = False

        self.last_gyro_notes_list = []
        self.last_accel_trigger_time = 0
        self.tones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def convert_to_midi_codes(self, notes_list): # [['C', 3], ['E', 3], ['G', 3]] 
        midi_codes = []
        for note in notes_list: # [['C', 3], ['E', 3], ['G', 3]] 
            for i in range(len(self.tones)): # for i in 12
                    if self.tones[i] == note[0]: # if 'C' == 'C' 
                        midi_codes.append( note[1] * len(self.tones) + i) # 3 * 12 + 0
        return midi_codes # [36, 40, 43]
    
    def play_notes(self, device, note_codes_list, pianissimo = False):
        for note_code in note_codes_list: # [36, 40, 43] 
            match device:
                case 'gyro':
                    if pianissimo:
                        print('pianissimo')
                        self.midiout.send_message([144, 
                                                note_code, # 36
                                                32])
                    else:
                        self.midiout.send_message([144, 
                                    note_code, # 36
                                    127])
                    self.last_gyro_notes_list = note_codes_list
                case 'accel':
                    self.midiout.send_message([145, 
                                    note_code, # 36
                                    100])
        print(f'Tocando {note_codes_list}')
    
    def stop_notes(self, device, note_codes_list):
        for note_code in note_codes_list: # [36, 40, 43]
            match device:
                case 'gyro':
                    self.midiout.send_message([128, 
                                        note_code, # 36
                                        100])
                    self.last_gyro_notes_list = note_codes_list
                case 'accel':
                    self.midiout.send_message([129, 
                                        note_code, # 36
                                        100])        
        print(f'Parando {note_codes_list}')  

    def set_gyro(self, gyro):
        self.gyro = gyro

    def set_touch(self, touch):
        if(not self.set_gyro):
            return
        self.touch = touch
        # Notas atuais
        current_notes = []
        for notes in self.config.get('angle_notes_list'): # [0, [['C', 3], ['E', 3], ['G', 3]]]
            notes_list = notes[1] 
            if self.gyro <= notes[0]: # TODO: testar limite infinito das notas
                break

        current_notes = self.convert_to_midi_codes(notes_list) 
        # current_notes == [36, 40, 43]

        if touch: 
            # Início do toque
            if not self.touch_flag:
                print('Início do toque')
                if self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_list)
                if touch == 2:
                    self.play_notes('gyro', current_notes, True) # pianissimo = True
                else:
                    self.play_notes('gyro', current_notes)

                self.touch_flag = True 
    
            # Decorrer do toque
            if current_notes != self.last_gyro_notes_list:
                print('Trocando de nota')
                self.stop_notes('gyro', self.last_gyro_notes_list)
                self.play_notes('gyro', current_notes)
        else:
            # Liberação do toque
            if self.touch_flag:
                print('Liberando toque')
                if not self.config.get('legato'): 
                    self.stop_notes('gyro', self.last_gyro_notes_list)
                self.touch_flag = False

    def set_accel(self, accel):
        self.accel = accel
        if time.time() - self.last_accel_trigger_time > self.config.get('accel_delay'):
            if abs(accel) > self.config.get('accel_sensitivity_+') or abs(accel) > self.config.get('accel_sensitivity_-'):
                if self.config.get('legato'): # Caso legato esteja ativado, a funcionalidade será interromper última nota
                    self.stop_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))     
                self.play_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                self.last_accel_trigger_time = time.time()
                self.accel_flag = True
            
            elif self.accel_flag:
                self.stop_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                self.accel_flag = False      

player = Player()

def gyro_notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_gyro(int.from_bytes(data, 'little', signed=True))

def accel_notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_accel(int.from_bytes(data, 'little', signed=True))

def touch_notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_touch(int.from_bytes(data, 'little', signed=False))


async def main(args: argparse.Namespace):
    with open(args.config_path) as jsonfile:
        player.config = json.load(jsonfile)
    player.midiout = rtmidi.MidiOut()
    player.midiout.open_port(1)
    print('Scan')

    if args.address:
        device = await BleakScanner.find_device_by_address(
            args.address)
        if device is None:
            print("Não foi possível encontrar de endereço'%s'", args.address)
            return
    else:
        device = await BleakScanner.find_device_by_name(
            args.name)
        if device is None:
            print("Não foi possível encontrar dispositivo de nome'%s'", args.name)
            return
        
    print("Conectando...")

    async with BleakClient(device) as client:
        print("Conectado")
        await client.start_notify(GYRO_CHARACTERISTIC_UUID, gyro_notification_handler)
        await client.start_notify(TOUCH_CHARACTERISTIC_UUID, touch_notification_handler) 
        await client.start_notify(ACCEL_CHARACTERISTIC_UUID, accel_notification_handler) 
        await asyncio.sleep(3600) # COMO QUE RODA INFINITO
        await client.stop_notify(GYRO_CHARACTERISTIC_UUID)
        await client.stop_notify(TOUCH_CHARACTERISTIC_UUID)
        await client.stop_notify(ACCEL_CHARACTERISTIC_UUID)


if __name__ == '__main__': # Convenção de Python: programa inicia aqui!
    # Argumentos do script
    parser = argparse.ArgumentParser()
    device_group = parser.add_mutually_exclusive_group(required=True)
    device_group.add_argument(
        '--name',
        metavar='<name>',
        help='Nome do dispositivo',
    )
    device_group.add_argument(
        '--address',
        metavar='<address>',
        help='Endereço do dispositivo',
    )
    parser.add_argument(
        '--config-path',
        metavar='<config_path>',
        help='Caminho para a JSON de configuração',
    )
    args = parser.parse_args()

    asyncio.run(main(args))