OBJ = $(patsubst %.cpp, %.o, $(wildcard *.cpp))
include ../Rule.mak

all: $(OBJ)
	$(CXX) -w -O2 $^ -o  pkcsdemo $(SHLIBS)
	#$(CXX) -g $^ -o  pkcsdemo $(SHLIBS)
$(OBJ): %.o : %.cpp
	$(CXX) -w -O2 -g -c $< -o $@
clean:
	rm -f pkcsdemo *.o
