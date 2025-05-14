import serial
import rtmidi.midiutil
import time
import rtmidi
import sys
import json

class Player:
    def __init__(self):
        self.config = None
        self.gyro_midiout = rtmidi.MidiOut().open_port(1)
        self.accel_midiout = rtmidi.MidiOut().open_port(2)

        # Sistema de flag assegura que condicionais só executem em mudanças de estado
        self.touch_flag = False
        self.accel_flag = False
        self.pianissimo_flag = False

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
    
    def play_notes(self, device, note_codes_list):
        for note_code in note_codes_list: # [36, 40, 43] 
            match device:
                case 'gyro':
                    if self.pianissimo_flag:
                        print('pianissimo')
                        self.gyro_midiout.send_message([143 + self.config.get('midiout_port'), 
                                                note_code, # 36
                                                32])
                    else:
                        self.gyro_midiout.send_message([143 + self.config.get('midiout_port'), 
                                    note_code, # 36
                                    127])
                    self.last_gyro_notes_list = note_codes_list
                case 'accel':
                    self.accel_midiout.send_message([143 + self.config.get('midiout_port'), 
                                    note_code, # 36
                                    100])
        print(f'Tocando {note_codes_list}')
    
    def stop_notes(self, device, note_codes_list):
        for note_code in note_codes_list: # [36, 40, 43]
            match device:
                case 'gyro':
                    self.gyro_midiout.send_message([127 + self.config.get('midiout_port'), 
                                        note_code, # 36
                                        100])
                    self.last_gyro_notes_list = note_codes_list
                case 'accel':
                    self.accel_midiout.send_message([127 + self.config.get('midiout_port'), 
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
                    self.pianissimo_flag = True
                else:
                    self.pianissimo_flag = False
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

def main():
    if len(sys.argv) > 2:
        config_path = sys.argv[1]
        com_port = 'COM' + sys.argv[2]

    with open(config_path) as jsonfile:
        config = json.load(jsonfile)

    rtmidi.midiutil.list_output_ports()
    serial_port = serial.Serial(port = com_port, 
                                baudrate=115200, 
                                bytesize=8, 
                                timeout=2, 
                                stopbits=serial.STOPBITS_ONE)
    player = Player(config)

    while(1):
        if(serial_port.in_waiting > 0):
            serial_string = serial_port.readline()
            sensor_data_list = (serial_string.decode('utf-8')).split('/')
            id = int(sensor_data_list[0])
            player.set_gyro(float(sensor_data_list[1]) * config.get('hand')) #TODO: Ver se gyro pode ser um int
            player.set_accel(float(sensor_data_list[2]))
            player.set_touch(int(sensor_data_list[3]))

            # Output
            print(f'{id} gyro: {player.gyro} acc: {player.accel} t: {player.touch}') 

if __name__ == '__main__': # Convenção de Python: programa inicia aqui!
    main()