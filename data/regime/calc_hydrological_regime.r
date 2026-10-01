Sys.setlocale("LC_MESSAGES", 'en_US.UTF-8')
Sys.setenv(LANG = "en_US.UTF-8")
####### calculate the annual and seasonal values

setwd("/Users/olgasilantyeva/projects/shyft-data/contrib/hydrology/catchment/Data")

#gauge <- c("16.66","22.22","21.47","6.10","2.323")
gauge <- c('109.29', '157.3', '107.3', '55.4', '109.9', '19.73', '12.192', '161.7', '2.303', '91.2', '152.4', '12.178', '213.2', '19.80', '172.7', '84.11', '104.23', '16.122', '153.1', '186.2', '177.4', '74.16', '19.82', '166.13', '223.2', '2.11', '111.9', '308.1', '124.2', '75.28', '122.11', '16.75', '86.10', '191.2', '206.3', '6.10', '27.26', '26.26', '133.7', '112.8', '3.22', '230.1', '26.20', '16.194', '24.8', '28.7', '122.14', '80.4', '200.4', '196.7', '2.28', '165.6', '138.1', '163.7', '2.279', '212.49', '189.3', '81.1', '41.1', '8.6', '2.284', '39.1', '185.1', '16.66', '148.2', '212.48', '22.22', '163.6', '105.1', '194.4', '50.1', '22.16', '2.323', '213.4', '178.1', '150.1', '2.267', '140.2', '2.32', '42.2', '11.4', '24.9', '139.20', '12.171', '82.4', '36.13', '111.10', '21.47', '128.5', '157.4', '15.49', '2.616', '2.607', '12.197', '151.13', '123.29', '26.21', '172.8', '2.280', '19.79', '62.10', '75.23', '84.20', '2.633', '128.9', '83.6', '19.96', '26.29', '168.3')

syear <- 1961
eyear <- 2019
nyear <- length(syear:eyear)

#time_total <- seq(ISOdate(syear,1,1),ISOdate(eyear,12,31),"day")
#year <- as.POSIXlt(time_total)$year+1900
#month <- as.POSIXlt(time_total)$mon+1

day_start <- ISOdate(syear,1,1)

day_end <- ISOdate(eyear,12,31)


qdata_mon <- matrix(rep(0,13*length(gauge)),nrow=length(gauge))

for ( i in 1:length(gauge)) {
ld<-0
# if(gauge[i,6]>0) {    ### change to 7 for 1971-2015
if ((gauge[i]=="109.29")|(gauge[i]=="157.3")|(gauge[i]=="107.3")|(gauge[i]=="55.4")|(gauge[i]=="109.9")|(gauge[i]=="19.73")|(gauge[i]=="12.192")|(gauge[i]=="161.7")|(gauge[i]=="2.303")|(gauge[i]=="91.2")|(gauge[i]=="12.178")|(gauge[i]=="213.2")|(gauge[i]=="19.80")|(gauge[i]=="172.7")|(gauge[i]=="104.23")|(gauge[i]=="16.122")|(gauge[i]=="153.1")|(gauge[i]=="177.4")|(gauge[i]=="74.16")|(gauge[i]=="19.82")|(gauge[i]=="111.9")|(gauge[i]=="308.1")|(gauge[i]=="124.2")|(gauge[i]=="75.28")|(gauge[i]=="122.11")|(gauge[i]=="16.75")|(gauge[i]=="86.10")|(gauge[i]=="6.10")|(gauge[i]=="112.8")|(gauge[i]=="3.22")|(gauge[i]=="230.1")|(gauge[i]=="26.20")|(gauge[i]=="28.7")|(gauge[i]=="122.14")|(gauge[i]=="80.4")|(gauge[i]=="196.7")|(gauge[i]=="165.6")|(gauge[i]=="138.1")|(gauge[i]=="163.7")|(gauge[i]=="2.279")|(gauge[i]=="189.3")|(gauge[i]=="81.1")|(gauge[i]=="41.1")|(gauge[i]=="8.6")|(gauge[i]=="2.284")|(gauge[i]=="39.1")|(gauge[i]=="185.1")|(gauge[i]=="16.66")|(gauge[i]=="148.2")|(gauge[i]=="22.22")|(gauge[i]=="163.6")|(gauge[i]=="194.4")|(gauge[i]=="50.1")|(gauge[i]=="2.323")|(gauge[i]=="213.4")|(gauge[i]=="178.1")|(gauge[i]=="150.1")|(gauge[i]=="2.267")|(gauge[i]=="42.2")|(gauge[i]=="139.20")|(gauge[i]=="12.171")|(gauge[i]=="36.13")|(gauge[i]=="111.10")|(gauge[i]=="21.47")|(gauge[i]=="128.5")|(gauge[i]=="157.4")|(gauge[i]=="15.49")|(gauge[i]=="151.13")|(gauge[i]=="26.12")|(gauge[i]=="26.21")|(gauge[i]=="172.8")|(gauge[i]=="2.280")|(gauge[i]=="19.79")|(gauge[i]=="75.23")|(gauge[i]=="83.6")|(gauge[i]=="19.96")|(gauge[i]=="26.29")|(gauge[i]=="168.3")){
  ld <- "1"
}
if ((gauge[i]=="206.3")|(gauge[i]=="105.1")){
  ld<-2
}
qdata <- read.table(paste("/Users/olgasilantyeva/projects/shyft-data/contrib/hydrology/catchment/Data/Q/",gauge[i],".0.1001.",ld,sep=""),  header=F,  na.strings = "-9999.000000")

#obs_time <- as.Date(qdata[,1], format='%Y-%m-%d')
obs_time <- as.Date(qdata[,1], format='%Y%m%d')
str("obs time:", obs_time)
obs_year <- as.POSIXlt(obs_time)$year+1900
month <- as.POSIXlt(obs_time)$mon+1
str(obs_year)
qdata[which(qdata[,2]<0),2] <- NA
str(qdata)

### calculate mon Q

  for ( j in 1:12) {
    qdata_mon[i,j] <- mean(qdata[which(obs_year>=syear&obs_year<=eyear&month==j),2],na.rm=T)
   }

lowq <- sort(qdata_mon[i,1:12])[1:2]
highq <- sort(qdata_mon[i,1:12])[10:12]
str(lowq)
str(highq)

n1 <- which(qdata_mon[i,1:12]==lowq[1])
n2 <- which(qdata_mon[i,1:12]==lowq[2])
n3 <- which(qdata_mon[i,1:12]==highq[1])
n4 <- which(qdata_mon[i,1:12]==highq[2])
n5 <- which(qdata_mon[i,1:12]==highq[3])

if(n1>=1&n1<=4&n2>=1&n2<=4&n3>=3&n3<=8&n4>=3&n4<=8&n5>=3&n5<=8) qdata_mon[i,13] <- 1   #mountain
if(n1>=1&n1<=4&n2>=1&n2<=4&n3>=9&n3<=11&n4>=3&n4<=8&n5>=3&n5<=8) qdata_mon[i,13] <- 2   # inland
if(n1>=1&n1<=4&n2>=1&n2<=4&n3>=3&n3<=8&n4>=9&n4<=11&n5>=3&n5<=8) qdata_mon[i,13] <- 2   # inland
if(n1>=6&n1<=10&n2>=6&n2<=10&(n5>=9|n5<=2)) qdata_mon[i,13] <- 3 #atlantic
if(n1>=6&n1<=10&n2>=6&n2<=10&(n3>=9|n3<=2)&n5>=3&n5<=5) qdata_mon[i,13] <- 4 #Baltic
if(n1>=6&n1<=10&n2>=6&n2<=10&(n4>=9|n4<=2)&n5>=3&n5<=5) qdata_mon[i,13] <- 4  # baltic

#####  0 indicates transition regime.


#} # end if
}  #end loop
print(qdata_mon)
out <- cbind(1:109,gauge, qdata_mon)
colnames(out) <- c("id","st_id",paste(1:12,"mon",sep=""),"regime")

write.table(out,"Q/mon_Q_regime.csv",row.names = F,
            col.names =T)



