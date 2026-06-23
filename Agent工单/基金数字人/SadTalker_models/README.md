---
tasks:
  - talking-head
widgets:
  - enable: true
    version: 1
    task: talking-head
    model_revision: v1.0.0
    inputs:
      - type: image
        displayType: ImageUploader
      - type: audio
        displayType: AudioUploader
    outputs:
      - type: video
    examples:
      - inputs:
          - data: https://raw.githubusercontent.com/wwdok/facechain/feat/add_sadtalker/resources/source_image/man.png
          - data: https://github.com/wwdok/facechain/raw/feat/add_sadtalker/resources/driven_audio/chinese_poem1.wav
      - inputs:
          - data: https://raw.githubusercontent.com/wwdok/facechain/feat/add_sadtalker/resources/source_image/woman.png
          - data: https://github.com/wwdok/facechain/raw/feat/add_sadtalker/resources/driven_audio/chinese_poem2.wav
    inferencespec:
      cpu: 1
      memory: 8000
      gpu: 1
      gpu_memory: 12000
domain:
  - cv
frameworks:
  - pytorch
backbone:
  - encoder-decoder
customized-quickstart: true
license: Apache License 2.0
tags:
  - sadtalker
  - talking head
  - 数字人

---

# SadTalker

本仓库是基于 https://github.com/OpenTalker/SadTalker （ed419f275f8a5cae7ca786349787ffebce5bd59e）改编而来。
本仓库的目的是将sadtalker仓库封装成成modelscope library，这样就能便用几行代码调用sadtalker的能力，方便集成到其他项目里，比如[facechain](https://github.com/modelscope/facechain)。

github版本：https://github.com/wwdok/sadtalker_modelscope 

关于SadTalker的技术原理解读，请见：[《2D数字人经典算法Wav2Lip和SadTalker简介》](https://zhuanlan.zhihu.com/p/666033822)

# 安装

1. 请确保您安装的modelscope版本大于1.9.1，否则会报错，请按照下面方式升级：
```
pip install -U modelscope
```
或者通过源码安装：
```
pip uninstall modelscope -y
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/modelscope/modelscope.git
cd modelscope
pip install -r requirements.txt
pip install .
```

2. 安装python依赖包：
```
numpy==1.23.4
face_alignment==1.3.5
imageio==2.19.3
imageio-ffmpeg==0.4.7
librosa
numba
resampy==0.3.1
pydub==0.25.1 
scipy==1.10.1
kornia==0.6.8
yacs==0.1.8
pyyaml  
joblib==1.1.0
scikit-image==0.19.3
basicsr==1.4.2
facexlib==0.3.0
gradio
gfpgan-patch
av
safetensors
easydict
```

3. 安装ffmpeg。你可以通过在命令行执行
```
ffmpeg -version
```
来判断是否已经安装ffmpeg，如果没有，可参考[这里](https://github.com/modelscope/facechain/blob/main/doc/installation_for_talkinghead_ZH.md#3%E5%AE%89%E8%A3%85ffmpeg)的安装ffmpeg的方法。


# 代码范例

```python
from modelscope.pipelines import pipeline

inference = pipeline('talking-head', model='wwd123/sadtalker', model_revision='v1.0.0') # 请使用最新版的model_revision
# 两个必须参数
source_image = 'examples/source_image/man.png' # 请修改成你的实际路径
driven_audio = 'examples/driven_audio/chinese_poem1.wav' # 请修改成你的实际路径
# 其他可选参数
out_dir = './results/' # 输出文件夹
kwargs = {
    'preprocess' : 'full', # 'crop', 'resize', 'full'
    'still_mode' : True,
    'use_enhancer' : False,
    'batch_size' : 1,
    'size' : 256, # 256, 512
    'pose_style' : 0,
    'exp_scale' : 1,
    'result_dir': out_dir
}

video_path = inference(source_image, driven_audio=driven_audio, **kwargs)
print(f"==>> video_path: {video_path}")
```

你可以在Colab上试玩：[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1C2TjndoDsUXlW6P10peN66p4I9ImEHyt?usp=sharing/)

## 参数说明

* `source_image`: 必填，要驱动的人脸图片的路径。
* `driven_audio`: 必填，且必须带上`driven_audio=`，驱动音频文件的路径，支持wav,mp3格式。
* `preprocess`：full：输出的视频帧跟原图一样大，crop：输出的视频帧只有裁剪后的人脸区域。
* `still_mode`: 设置为True会减少头部运动。
* `use_enhancer`: 是否使用GFPGAN对人脸增强，即增加清晰度。
* `batch_size`: 该值代表了Face Renderer阶段并行处理的批次数，因为这一阶段是最耗时的。比如batch size=1时，Face Renderer需要100个时间步，batch size=10时，Face Renderer仅需要10个时间步，但是batch size增大有两个问题，第一，GPU显存占用增大，第二，预处理会占用时间，只有当需要合成的视频比较长时，增大batch size才有用。
* `size`: 人脸裁剪成的大小。
* `pose_style`: 是Conditional VAE（即PoseVAE）的条件输入，使用的地方最终位于src/audio2pose_models/cvae.py里的`class DECODER`的`def forward`。
* `exp_scale`: 越大的话表情越夸张。
* `result_dir`: 结果输出路径。

