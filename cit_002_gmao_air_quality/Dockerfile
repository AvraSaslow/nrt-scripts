FROM python:3.6
MAINTAINER Amelia Snyder <amelia.snyder@wri.org>
#Note this script was originally developed by Amelia Snyder <amelia.snyder@wri.org>

# install core libraries
RUN apt-get update
RUN pip install -U pip

# install application libraries
RUN apt-get install -y gdal-bin libgdal-dev
RUN pip install oauth2client==4.1.3
RUN pip install google-api-python-client==1.12.8
RUN pip install -e git+https://github.com/resource-watch/eeUtil#egg=eeUtil
RUN pip install netCDF4==1.5.3
RUN pip install bs4==0.0.1
RUN pip install numpy==1.18.1

# set name
ARG NAME=nrt-script
ENV NAME ${NAME}

# copy the application folder inside the container
RUN mkdir -p /opt/$NAME/data
WORKDIR /opt/$NAME/
COPY contents/ .

RUN useradd -r $NAME
RUN chown -R $NAME:$NAME /opt/$NAME
USER $NAME

CMD ["python", "main.py"]
