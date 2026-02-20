# AI System Inventory
Generated: Fri Feb 20 12:35:32 PM MST 2026

## Host / OS
Linux AIExperimental 6.17.0-14-generic #14~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Thu Jan 15 15:52:10 UTC 2 x86_64 x86_64 x86_64 GNU/Linux

## Disk / Mounts
Filesystem                                   Size  Used Avail Use% Mounted on
tmpfs                                         19G  6.0M   19G   1% /run
/dev/nvme1n1p5                               2.4T  663G  1.6T  30% /
tmpfs                                         95G  882M   94G   1% /dev/shm
tmpfs                                        5.0M   16K  5.0M   1% /run/lock
efivarfs                                     256K  135K  117K  54% /sys/firmware/efi/efivars
/dev/nvme1n1p1                                96M   38M   59M  39% /boot/efi
/dev/nvme0n1p1                               3.7T  487G  3.1T  14% /ai_data
//192.168.2.87/Downloads_Entire_Network_NAS  3.7T  2.4T  1.4T  65% /mnt/Downloads_Entire_Network_NAS
//192.168.2.87/Docker                        3.7T  2.4T  1.4T  65% /mnt/Docker
tmpfs                                         19G  172K   19G   1% /run/user/1000

## GPU
Fri Feb 20 12:35:32 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.126.09             Driver Version: 580.126.09     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 5090        Off |   00000000:01:00.0  On |                  N/A |
|  0%   41C    P8             30W /  575W |    1250MiB /  32607MiB |      3%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A            3267      G   /usr/lib/xorg/Xorg                      916MiB |
|    0   N/A  N/A            3437      G   /usr/bin/gnome-shell                     71MiB |
|    0   N/A  N/A            4362      G   ...rack-uuid=3190708988185955192        164MiB |
|    0   N/A  N/A         2857641      G   /usr/bin/nautilus                        15MiB |
|    0   N/A  N/A         2858681      G   /usr/bin/gnome-text-editor               18MiB |
+-----------------------------------------------------------------------------------------+

## Python
Python 3.12.3
pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.12)

## Virtual Environments
/home/mario/ai-env/lib/python3.12/site-packages/jedi/third_party/typeshed/stdlib/3/venv
/home/mario/ai-ebooks-venv
/home/mario/ai-workspace/venv
/home/mario/FineTuningAI/venvs

## Ollama Models
NAME                                                            ID              SIZE      MODIFIED     
enoch-md:latest                                                 7f57e9c8f6b3    7.5 GB    5 weeks ago     
gemma-md:latest                                                 966274d24de5    17 GB     5 weeks ago     
qwen-md:latest                                                  b3857816ce81    9.0 GB    5 weeks ago     
command-r:latest                                                7d96360d357f    18 GB     5 weeks ago     
qwen2.5:14b                                                     7cdf5a0187d5    9.0 GB    5 weeks ago     
enoch:latest                                                    ae454063de58    7.5 GB    5 weeks ago     
huggingface.co/CWClabs/CWC-Mistral-Nemo-12B-V2-q4_k_m:latest    3002c387d492    7.5 GB    6 weeks ago     
deepcoder:14b                                                   12bdda054d23    9.0 GB    3 months ago    
codegemma:7b                                                    0c96700aaada    5.0 GB    3 months ago    
gemma3:27b                                                      a418f5838eaf    17 GB     3 months ago    
gemma3:12b                                                      f4031aab637d    8.1 GB    3 months ago    
codellama:13b                                                   9f438cb9cd58    7.4 GB    3 months ago    
nous-hermes2:34b                                                1fbb49caabbd    19 GB     3 months ago    
LLaMa3.1:8b                                                     46e0c10c039e    4.9 GB    3 months ago    
deepseek-r1:7b                                                  755ced02ce7b    4.7 GB    3 months ago    
deepseek-r1:32b                                                 edba8017331d    19 GB     3 months ago    
mixtral:8x7b                                                    a3b6bef0f836    26 GB     3 months ago    
qwen3-vl:32b                                                    ff2e46876908    20 GB     3 months ago    
llama2:latest                                                   78e26419b446    3.8 GB    3 months ago    

## AI Corpus
0	/home/mario/ai_corpus

