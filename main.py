import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import time

ser = serial.Serial(port='COM4', baudrate=921600, timeout=1, parity=serial.PARITY_NONE,
                    bytesize=serial.EIGHTBITS, rtscts=1)


def validity_check(signal):
    # ASCII code for "<" is 60, and for ">" it is 62
    # If the message starts with "<<" and ends with ">>"
    if signal[0] == 60 and signal[1] == 60 and signal[-1] == 62 and signal[-2] == 62:
        checksum = signal[2] ^ signal[3] ^ signal[4] ^ signal[5] ^ signal[6] ^ signal[7] ^ signal[8] ^ signal[9]
        # If the XOR value equals the value of the checksum byte
        if checksum == signal[10]:
            return True
        else:
            return False
    else:
        return False


def conversion_AD_units_into_voltage(signal, test_mode):
    reference_v = 4.5
    amp_gain = 24
    C1_AD = (signal[2] << 16) | (signal[3] << 8) | (signal[4])
    if C1_AD >= 8388608:
        C1_AD = C1_AD - 16777216

    C2_AD = 0
    if not test_mode:
        C2_AD = (signal[5] << 16) | (signal[6] << 8) | (signal[7])
        if C2_AD >= 8388608:
            C2_AD = C2_AD - 16777216

    scale_factor_uV = 1000000 * ((reference_v / (8388608 - 1)) / amp_gain)

    return C1_AD * scale_factor_uV, C2_AD * scale_factor_uV


def animation(i, signal1, signal2, step, test_mode, win=None, over=None):
    if len(signal1) > 1:
        i += 1
    for j in range(step):
        data = ser.read(13)
        if validity_check(data):
            result = conversion_AD_units_into_voltage(data, test)
            signal1.append(result[0])
            if test_mode:
                signal2.append(data[8])

    tr = np.linspace(0, i+1, len(signal1))
    ax2.clear()
    ax3.clear()
    ax2.plot(tr, signal1, linewidth=0.5)
    if test_mode:
        ax3.plot(tr, signal2, linewidth=0.5)
    else:
        ax3.plot(tr, signal1, linewidth=0.5)
        for k in range(0, len(signal1) - win//2, win - over):
            rms = np.sqrt(np.mean(np.abs(signal1[k:k + win]) ** 2))
            signal2[k:k + win] = rms * np.ones(len(signal2[k:k + win]))
        ax3.plot(tr, signal2[:len(tr)], linewidth=1)


if __name__ == '__main__':
    # Setting up constants
    power_supply = False
    acquisition = False
    test = False
    Fs = 0

    # Turn ON power supply for EMG amplifiers
    if not acquisition and not power_supply:
        # ser.write(b'<<CH1:ON>>\n')
        # ser.write(b'<<CH2:ON>>\n')
        ser.write(b'<<CHs:ON>>\n')
        status = ser.read(6)
        if status == b'<<OK>>':
            power_supply = True

    if not acquisition and power_supply:
        # Set sampling frequency
        # ser.write(b'<<F:250>>\n')
        ser.write(b'<<F:500>>\n')
        status = ser.read(6)
        if status == b'<<OK>>':
            Fs = 500

        # Turn TEST mode ON
        ser.write(b'<<TEST>>\n')
        status = ser.read(6)
        if status == b'<<OK>>':
            test = True
            # Start EMG acquisition
            ser.write(b'<<START>>\n')
            status = ser.read(6)
            if status == b'<<OK>>':
                acquisition = True
                emg_ch1_data = []
                counter = []

                # Online mode
                duration = 10
                length = duration * Fs
                t = np.linspace(0, duration, length)
                fig_rt, (ax2, ax3) = plt.subplots(2, 1)
                smpl_per_sec = int(len(t) // t[-1])
                ani = FuncAnimation(fig_rt, animation, fargs=(emg_ch1_data, counter, smpl_per_sec, test), frames=9,
                                    interval=1000, repeat=False)
                plt.show()

                # Stop EMG acquisition
                if acquisition and power_supply:
                    ser.write(b'<<STOP>>\n')
                    ser.reset_output_buffer()
                    time.sleep(0.1)
                    while ser.read(13) != b'<<OK>>':
                        ser.read(13)
                    acquisition = False

                # Offline mode
                fig, (ax0, ax1) = plt.subplots(2, 1)
                ax0.plot(t, emg_ch1_data, linewidth=0.5)
                ax0.set_title('EMG CHANNEL 1 DATA')
                ax0.set_xlabel('Time [s]')
                ax0.set_ylabel('Value')
                ax1.plot(t, counter, linewidth=0.5)
                ax1.set_xlabel('Time [s]')
                ax1.set_ylabel('Value')
                ax1.set_title('COUNTER')
                plt.show()
                test = False

        # Turn NORMAL mode ON
        ser.write(b'<<NORMAL>>\n')
        status = ser.read(6)
        if status == b'<<OK>>':
            # Start EMG acquisition
            ser.write(b'<<START>>\n')
            status = ser.read(6)
            if status == b'<<OK>>':
                acquisition = True
                ch1_data = []
                ch2_data = []

                data = ser.read(13)
                if data == b'<<\x00\x00\x11\x00\x00\x00\x01ZJ>>':  # First sample in DATA 1d
                    duration = 90
                    length = duration * Fs
                    title = "EMG DATA 1d"
                elif data == b'<<\x00\x00%\x00\x00\x00\x01Y}>>':  # First sample in DATA 2d
                    duration = 33
                    length = duration * Fs
                    title = "EMG DATA 2d"
                elif data == b'<<\x00\x00\x0f\x00\x00\x00\x01VX>>':  # First sample in DATA 3d
                    duration = 15
                    length = duration * Fs
                    title = "EMG DATA 3d"
                else:
                    length = 0
                    duration = 0
                    title = ""

                # Setup for envelope calculation
                rms_ch1 = np.zeros(length)
                rms_ch2 = np.zeros(length)
                window = length//150  # Number of samples based on which RMS is calculated
                overlap = window//2  # Number of points in which two consecutive windows overlap

                # Online mode
                t = np.linspace(0, duration, length)
                fig_rt, (ax2, ax3) = plt.subplots(2, 1)
                smpl_per_sec = int(len(t) // duration)
                ani = FuncAnimation(fig_rt, animation, fargs=(ch1_data, rms_ch1, smpl_per_sec, test, window, overlap),
                                    frames=duration-1, interval=1000, repeat=False,)
                plt.show()

                # Stop EMG acquisition
                if acquisition and power_supply:
                    ser.write(b'<<STOP>>\n')
                    ser.reset_output_buffer()
                    time.sleep(0.1)
                    while ser.read(13) != b'<<OK>>':
                        ser.read(13)
                    acquisition = False

                # Offline mode
                t = np.linspace(0, duration, length)
                fig, (ax0, ax1) = plt.subplots(2, 1)
                ax0.plot(t, ch1_data, linewidth=0.5)
                ax0.set_xlabel('Time [s]')
                ax0.set_ylabel('Value [mV]')
                ax0.set_title(title)
                ax1.plot(t, ch1_data, linewidth=0.5)
                ax1.plot(t, rms_ch1, linewidth=1)
                ax1.set_xlabel('Time [s]')
                ax1.set_ylabel('Value [mV]')
                ax1.set_title(title + " envelope")
                plt.savefig(title + ".png")
                plt.show()

    # Turn OFF power supply for EMG amplifiers
    if not acquisition and power_supply:
        # ser.write(b'<<CH1:OFF>>\n')
        # ser.write(b'<<CH2:OFF>>\n')
        ser.write(b'<<CHs:OFF>>\n')
        status = ser.read(6)
        if status == b'<<OK>>':
            power_supply = False
