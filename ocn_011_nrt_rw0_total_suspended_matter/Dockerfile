FROM python:3.6
MAINTAINER Yujing Wu <yujing.wu@wri.org>
#Note this script was originally developed by Peter Kerins <Peter.Kerins@wri.org>

# install core libraries
RUN apt-get update
RUN pip install -U pip

# install application libraries
RUN apt-get install -y gdal-bin libgdal-dev
RUN pip install oauth2client==4.1.3
RUN pip install -e git+https://github.com/resource-watch/eeUtil#egg=eeUtil
RUN pip install requests==2.22.0
RUN pip install numpy==1.14.3
RUN pip install Cython==0.29.15

# set name
ARG NAME=ocn_011_total_suspended_matter
ENV NAME ${NAME}

# copy the application folder inside the container
RUN mkdir -p /opt/$NAME/data
WORKDIR /opt/$NAME/
COPY contents/ .

RUN useradd -r $NAME
RUN chown -R $NAME:$NAME /opt/$NAME
USER $NAME

CMD ["python", "main.py"]
