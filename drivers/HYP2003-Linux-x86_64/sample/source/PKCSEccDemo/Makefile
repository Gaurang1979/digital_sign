OBJ = $(patsubst %.cpp, %.o, $(wildcard *.cpp))
include ../Rule.mak

all: $(OBJ)
	#$(CXX) -O2 $^ -o  pkcsdemo $(SHLIBS)
	$(CXX) -w -g $^ -o  pkcseccdemo $(SHLIBS)
$(OBJ): %.o : %.cpp
	$(CXX) -w -O2 -g -c $< -o $@
clean:
	rm -f pkceccsdemo *.o
