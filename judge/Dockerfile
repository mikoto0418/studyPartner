# 判题沙箱镜像。
#
# 官方 criyle/go-judge 镜像只带沙箱本体，不含任何语言运行时；而本项目的编程题
# 支持 python / javascript / java，判题时直接调用 /usr/bin/python3、/usr/bin/node、
# /usr/bin/javac。所以必须自己基于官方镜像装运行时，否则所有编程题都会判成
# 「找不到解释器 / 编译失败」。
FROM criyle/go-judge:latest AS go-judge

FROM debian:latest
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    nodejs \
    default-jdk-headless \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
COPY --from=go-judge /opt/go-judge /opt/mount.yaml /opt/

EXPOSE 5050/tcp
ENTRYPOINT ["./go-judge"]