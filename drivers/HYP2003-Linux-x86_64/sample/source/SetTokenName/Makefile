OBJ := $(patsubst %.cpp,%.o,$(wildcard *.cpp))
include ../Rule.mak
all: $(OBJ)
	$(CXX) -w $^  $(SHLIBS) -o settokenname -ldl
$(OBJ) : %.o : %.cpp
	$(CXX) -w -c $< -o $@ 
clean:
	rm -f settokenname *.o core
