## winpy.py - Manipulate WIN files
## Sample code to outout csv files of WIN data
## Apr 05, 2021  Yasunori Sawaki

import sys
import os
from pathlib import Path
import argparse
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt

import obspy as ob


class WinTools():
    """Manipulate WIN files.
    
    Usage:
    ------
    >>> from winpy import WinTools
    >>> wt = WinTools()
    >>> st = wt.read('sample.win')
    >>> wt.write('out.csv','CSV',decimate=10)
    
    Note:
        This program was coded by Y. Sawaki. 
        The original program was coded by Dr. M. Naoi.
    """
    def __init__(self):
        self.stream = None
        
    def read(
        self, filepath, IDs=None, 
        respAD=1.02084*10**-7, sensitivity=70.,
    ):
        """Read an WIN file to create obspy.Stream object.
        
        Parameters:
        -----------
        filepath : str or pathlib.Path
            A filename to save data
        IDs : list, default to None
            Select channel IDs to load.
            If None, all channels will be loaded.
        respAD : float
            Voltage per digit [V/counts].
            If None, will be 1.
        sensitivity : float
            Sensitivity of seismometers [V/(m/s)].
            Unit will be [nm] when attached the sensitivity.
            If None, no sensitivity will be fixed.
            
        """
        
        if IDs:
            IDs = [s.lower() for s in IDs]
          
        self.respAD = respAD if respAD else 1.
        
        if sensitivity:
            self.sensitivity = sensitivity
            self.nanometer = 10**9
        else:
            self.sensitivity = self.nanometer = 1.
        
        self.filepath = Path(filepath)
        
        ## Load all data as `._buffer`
        with self.filepath.open('rb') as f:
            self._buffer = f.read()
            
        self._offset = 0
        iteration = 0
        final_iteration = defaultdict(lambda: 0)
        self.output_data = defaultdict(lambda: dict(data=None, sampling_rate=None))
        
        while self._offset < len(self._buffer):
            
            starttime = self._load_header_second()
            if iteration == 0:
                self._starttime = starttime
            iteration += 1
            
            fixed_bulk = self._blocksize + self._offset - 10
            while self._offset < fixed_bulk:
                
                chID = self._load_header_channel()
                
                self._calc_bytes_in_sample()
                
                if IDs and (not chID in IDs):
                    self._offset += self._total_bytes_wav
                    continue
                    
                ## Waveforms
                self._wav_buffer = self._buffer[self._offset:self._offset+self._total_bytes_wav]
                self._convert_buffer_to_wav()
                self._offset += self._total_bytes_wav
                
                ## output 
                if (chID in self.output_data) or (iteration != 0) :
                    dt = iteration - final_iteration[chID] - 1
                    if dt > 0:
                        nanarray = np.empty(dt*self.sample_rate) * np.nan
                        self._wavdata = np.hstack([nanarray, self._wavdata])
                
                if chID in self.output_data:
                    self.output_data[chID]['data'] = np.hstack([
                        self.output_data[chID]['data'], self._wavdata
                    ])
                else:
                    self.output_data[chID]['data'] = self._wavdata
                    self.output_data[chID]['sampling_rate'] = self.sample_rate

                final_iteration[chID] = iteration
        
        self._create_stream()
        self._clean()
        return self.stream
        
    def _load_header_second(self):
        
        self._blocksize = int.from_bytes(
            self._buffer[self._offset:self._offset+4], byteorder='big'
        )
        self._offset += 4
        
        buffer_date = self._buffer[self._offset:self._offset+6]
        self._offset += 6
        
        ## Output starttime
        return ob.UTCDateTime(
            int(f'20'+buffer_date[:1].hex()), 
            *[int(f'{b:x}') for b in buffer_date[1:6]]
        )
        
    def _load_header_channel(self):
        
        buffer_channel = self._buffer[self._offset:self._offset+4]
        self._offset += 4
        
        chID = buffer_channel[:2].hex()
        
        _tmp = buffer_channel[2:].hex()
        self.sample_size = int(_tmp[0], 16)
        self.sample_rate = int(_tmp[1:], 16)
        
        return chID
    
    def _calc_bytes_in_sample(self):
        
        bytes_per_sample = self._load_data_byte(self.sample_size)
        
        ## Total bytes in waveform - Round up to int 
        self._total_bytes_wav = 4 + -int((-bytes_per_sample*(self.sample_rate-1))//1)
            
    def _load_data_byte(self, size):
        
        if size == 0:
            bytes_per_sample = 0.5
        elif size == 5:
            bytes_per_sample = 4
        else:
            bytes_per_sample = size
            
        return bytes_per_sample
        
    def _convert_buffer_to_wav(self):
        
        #sys.stdout.write(f'{self.sample_size}')
        
        if self.sample_size == 5:
            wav_data = np.frombuffer(
                self._wav_buffer, dtype='>i4', count=self.sample_rate-1,  offset=0
            )
            
        else: ## not 5
            
            ## Load initial value separately
            if self.sample_size == 3:
                initial_value = np.frombuffer(
                    self._wav_buffer[:4], 
                    dtype='>i4', count=1,  offset=0
                )
            else:
                initial_value = np.frombuffer(
                    self._wav_buffer, 
                    dtype='>i4', count=1,  offset=0
                )
                
            ## Wave data
            if self.sample_size == 0:
                
                _tmp = np.frombuffer(
                    self._wav_buffer, 
                    dtype='>i1', 
                    count=-((1-self.sample_rate)//2), offset=4,
                )       
                wav_data = np.vstack([_tmp>>4,_tmp<<4>>4]).T.reshape(-1,)
                
            elif self.sample_size == 3:
                wav_data = np.array([
                    int.from_bytes(self._wav_buffer[3*i+4:3*i+7],'big',signed=True) 
                    for i in range(self.sample_rate-1)
                ])
                
            else:  # [1,2,4]
                wav_data = np.frombuffer(
                    self._wav_buffer, 
                    dtype=f'>i{self.sample_size}', 
                    count=self.sample_rate-1, offset=4,
                )
            
            self._wavdata = np.cumsum(
                np.hstack([initial_value, wav_data])
            )
            
    def _create_stream(self):
        
        self.stream = ob.Stream()
        
        for (k, v) in self.output_data.items():
            tr = ob.Trace(
                data=v['data']*self.respAD/self.sensitivity*self.nanometer
            )
            tr.stats.update(dict(
                channel=k, sampling_rate=v['sampling_rate'],
                starttime=self._starttime
            ))
            self.stream += tr
            
    def write(self, filename, format='CSV', decimate=None, **kwargs):
        """Save stream as a file in various formats.
        
        Parameters:
        -----------
        filename : str or pathlib.Path
            A filename to save data
        format : str, default to 'CSV'
            'CSV' or other formats ('WAV','SAC','pickle'...)
            For details, see https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.write.html
        decimate : int, default to None
            If integer from 2 to 16, decimate output file.
            "Decimation" means number of data reducing by 1/n. 
        """
        try:
            if format.upper() == 'CSV':
                save_as_csv(filename, self.stream, decimate)
            else:
                self.stream.write(filename, format=format, **kwargs)
        except NameError:
            raise Exception('No stream found. Call `.read()` first.')
            
    def _clean(self):
        
        try:
            del (
                self._blocksize, self._buffer, self._offset,
                self._total_bytes_wav, self._wav_buffer,
                self.sample_size, self.sample_rate,
                self._wavdata, self._starttime
            )
        except NameError:
            pass
        
def save_as_csv(filename, stream, decimate=None):
    
    st = stream.copy()
    if decimate:
        st.decimate(factor=decimate)
       
    with open(filename, 'w') as f:
        f.write(
            f"# STATION {st[0].stats.station}\n"+
            f"# START_TIME {str(st[0].stats.starttime)}\n"+
            f"# SAMPING_FREQ {st[0].stats.sampling_rate:.1f}\n"+
            f"# NDAT {st[0].stats.npts}\n"
        )
        np.savetxt(
            f, np.vstack([st[0].times()]+[tr.data for tr in st]).T, 
            delimiter=',', #comments='#'
            header='time [s],'+','.join([tr.stats.channel for tr in st])
        )
        
        
__author__ = 'Yasunori Sawaki'
__status__ = "production"
__date__ = "Apr 05, 2021"
__version__ = "0.1.0"


if __name__ == '__main__':
    
    ## Parser
    parser = argparse.ArgumentParser(description='Creating CSV files of selected WIN files.')

    parser.add_argument('files', nargs='*', help='File names or paths to manipulate')
    parser.add_argument('-o', '--outpath', default='./output', help='Directory path for output files.')
    
    args = parser.parse_args()
    
    filepaths = [Path(p) for p in args.files]
    outpath = Path(args.outpath)
        
    ## Main
    wt = WinTools()
    
    for p in filepaths:
        
        ## Read a file
        sys.stdout.write(f'\nNow loading {str(p)} ...\n')
        wt.read(p)
        
        ## Write as CSV
        sys.stdout.write(f'Creating CSV file for {str(p)} under "{str(outpath)}"\n')
        wt.write(outpath/f'{p.name}.csv', decimate=10)
                

