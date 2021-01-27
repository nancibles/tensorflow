import argparse
import subprocess
import tensorflow as tf
import binascii


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", "-u")
    args = parser.parse_args()
    username = args.username

    subprocess.call("python data_prepare_flourish.py --website=True --username=%s"%username, shell=True)
    subprocess.call("python data_split.py", shell=True)
    #subprocess.call("python train.py --model=CNN --person=False --outfile='SampleTestData'", shell=True)
    print("done subprocess call...")
    subprocess.call("apt-get -qq install xxd", shell=True)
    subprocess.call("xxd -i model_lfg.tflite > model_lfg.cc", shell=True)
    #model_file = open("model_%s.tflite"%"lfg", 'r')
    #hex_file = binascii.b2a_hex(model_file)

    with open('model_lfg.tflite', 'r') as f:
        hexdata = hex(f.read())
        print(hexdata)
